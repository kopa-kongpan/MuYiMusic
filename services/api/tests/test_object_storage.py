from uuid import uuid4

import pytest

from app.core.config import Settings
from app.providers.object_storage import (
    MediaFileTooLargeError,
    ObjectStorageProvider,
    UnsupportedMediaTypeError,
)


def storage_settings() -> Settings:
    return Settings(
        _env_file=None,
        object_storage_provider="cos",
        object_storage_endpoint="https://cos.example.com",
        object_storage_region="ap-singapore",
        object_storage_bucket="music-assets",
        object_storage_access_key_id="test-access-key",
        object_storage_secret_access_key="test-secret-key",
        object_storage_public_base_url="https://media.example.com",
    )


def test_object_storage_creates_real_s3_presigned_put() -> None:
    store_id = uuid4()
    ticket = ObjectStorageProvider(storage_settings()).create_upload_ticket(
        store_id=store_id,
        file_name="门店 环境.jpg",
        content_type="image/jpeg",
        file_size=1024,
    )

    assert ticket.object_key.startswith(f"muyimusic/stores/{store_id}/home/")
    assert ticket.object_key.endswith(".jpg")
    assert "X-Amz-Signature=" in ticket.upload_url
    assert "X-Amz-Security-Token" not in ticket.upload_url
    assert ticket.headers["Content-Type"] == "image/jpeg"
    assert ticket.public_url == (f"https://media.example.com/{ticket.object_key}")


def test_object_storage_rejects_oversized_media() -> None:
    settings = storage_settings()
    settings.object_storage_max_image_bytes = 100
    provider = ObjectStorageProvider(settings)

    with pytest.raises(MediaFileTooLargeError) as error:
        provider.create_upload_ticket(
            store_id=uuid4(),
            file_name="large.png",
            content_type="image/png",
            file_size=101,
        )

    assert error.value.max_size_bytes == 100


def test_object_storage_uses_product_scope_for_product_images() -> None:
    store_id = uuid4()
    provider = ObjectStorageProvider(storage_settings())
    ticket = provider.create_upload_ticket(
        store_id=store_id,
        file_name="course.jpg",
        content_type="image/jpeg",
        file_size=1024,
        purpose="product",
    )

    assert ticket.object_key.startswith(f"muyimusic/stores/{store_id}/products/")
    assert provider.is_product_object_key(store_id, ticket.object_key)
    assert not provider.is_home_object_key(store_id, ticket.object_key)

    with pytest.raises(UnsupportedMediaTypeError):
        provider.create_upload_ticket(
            store_id=store_id,
            file_name="course.mp4",
            content_type="video/mp4",
            file_size=1024,
            purpose="product",
        )


def test_object_storage_product_video_scope_accepts_video_only() -> None:
    store_id = uuid4()
    provider = ObjectStorageProvider(storage_settings())
    ticket = provider.create_upload_ticket(
        store_id=store_id,
        file_name="第一章.mp4",
        content_type="video/mp4",
        file_size=1024,
        purpose="product_video",
    )

    assert ticket.object_key.startswith(f"muyimusic/stores/{store_id}/products/videos/")
    assert ticket.object_key.endswith(".mp4")
    assert provider.is_product_video_object_key(store_id, ticket.object_key)
    assert provider.is_product_object_key(store_id, ticket.object_key)

    with pytest.raises(UnsupportedMediaTypeError):
        provider.create_upload_ticket(
            store_id=store_id,
            file_name="cover.jpg",
            content_type="image/jpeg",
            file_size=1024,
            purpose="product_video",
        )


def test_object_storage_presigned_get_url_signs_get_requests() -> None:
    settings = storage_settings()
    settings.object_storage_public_base_url = None
    provider = ObjectStorageProvider(settings)
    store_id = uuid4()
    ticket = provider.create_upload_ticket(
        store_id=store_id,
        file_name="chapter.mp4",
        content_type="video/mp4",
        file_size=1024,
        purpose="product_video",
    )

    url = provider.presigned_get_url(ticket.object_key)
    assert url is not None
    assert "X-Amz-Signature=" in url
    assert "X-Amz-Security-Token" not in url
    assert "get_object" not in url  # 签名 URL 不暴露操作名

    assert ticket.public_url == url
