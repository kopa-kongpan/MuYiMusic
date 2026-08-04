from uuid import uuid4

import pytest

from app.core.config import Settings
from app.providers.object_storage import (
    MediaFileTooLargeError,
    ObjectStorageProvider,
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
