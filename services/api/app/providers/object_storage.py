from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from pathlib import PurePosixPath
from typing import Any, Protocol
from urllib.parse import quote
from uuid import UUID, uuid4

import boto3
from botocore.config import Config

from app.core.config import Settings, get_settings

ALLOWED_IMAGE_CONTENT_TYPES = {
    "image/gif": ".gif",
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}
ALLOWED_VIDEO_CONTENT_TYPES = {
    "video/mp4": ".mp4",
    "video/quicktime": ".mov",
    "video/webm": ".webm",
}
SUPPORTED_PROVIDERS = {"cos", "oss", "tos", "s3"}


class S3Client(Protocol):
    def generate_presigned_url(
        self,
        ClientMethod: str,
        Params: dict[str, Any],
        ExpiresIn: int,
        HttpMethod: str | None = None,
    ) -> str: ...


class ObjectStorageNotConfiguredError(Exception):
    pass


class UnsupportedMediaTypeError(Exception):
    pass


class MediaFileTooLargeError(Exception):
    def __init__(self, max_size_bytes: int) -> None:
        self.max_size_bytes = max_size_bytes


@dataclass(frozen=True)
class UploadTicket:
    object_key: str
    upload_url: str
    public_url: str | None
    headers: dict[str, str]
    expires_at: datetime
    max_size_bytes: int


class ObjectStorageProvider:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._client: S3Client | None = None

    def _configured_client(self) -> S3Client:
        provider = (self.settings.object_storage_provider or "").lower()
        if provider not in SUPPORTED_PROVIDERS:
            raise ObjectStorageNotConfiguredError
        if not self.settings.has_object_storage_credentials():
            raise ObjectStorageNotConfiguredError
        if self.settings.object_storage_addressing_style not in {"virtual", "path"}:
            raise ObjectStorageNotConfiguredError
        if self._client is None:
            self._client = boto3.client(
                "s3",
                endpoint_url=self.settings.object_storage_endpoint,
                region_name=self.settings.object_storage_region,
                aws_access_key_id=self.settings.object_storage_access_key_id,
                aws_secret_access_key=self.settings.object_storage_secret_access_key,
                aws_session_token=(self.settings.object_storage_session_token or None),
                config=Config(
                    signature_version="s3v4",
                    s3={
                        "addressing_style": (
                            self.settings.object_storage_addressing_style
                        )
                    },
                ),
            )
        return self._client

    def presigned_get_url(self, object_key: str) -> str | None:
        """恒签名 GET 地址（用于受保护内容，不经过公开直链）。"""
        try:
            client = self._configured_client()
        except ObjectStorageNotConfiguredError:
            return None
        bucket = self.settings.object_storage_bucket
        if bucket is None:
            return None
        return str(
            client.generate_presigned_url(
                "get_object",
                Params={"Bucket": bucket, "Key": object_key},
                ExpiresIn=self.settings.object_storage_download_expires_seconds,
            )
        )

    def media_url(self, object_key: str | None) -> str | None:
        if not object_key:
            return None
        public_base_url = self.settings.object_storage_public_base_url
        if public_base_url:
            encoded_key = "/".join(
                quote(part, safe="") for part in object_key.split("/")
            )
            return f"{public_base_url.rstrip('/')}/{encoded_key}"
        return self.presigned_get_url(object_key)

    def create_upload_ticket(
        self,
        *,
        store_id: UUID,
        file_name: str,
        content_type: str,
        file_size: int,
        purpose: str = "home_content",
    ) -> UploadTicket:
        client = self._configured_client()
        extension, max_size_bytes = self._validate_media(content_type, file_size)
        if purpose == "product" and content_type not in ALLOWED_IMAGE_CONTENT_TYPES:
            raise UnsupportedMediaTypeError
        if (
            purpose == "product_video"
            and content_type not in ALLOWED_VIDEO_CONTENT_TYPES
        ):
            raise UnsupportedMediaTypeError
        key_prefix = self.settings.object_storage_path_prefix.strip("/")
        if purpose == "product":
            directory = "products"
        elif purpose == "product_video":
            directory = "products/videos"
        else:
            directory = "home"
        object_path = PurePosixPath(
            key_prefix,
            "stores",
            str(store_id),
            directory,
            f"{uuid4().hex}{extension}",
        )
        object_key = str(object_path)
        bucket = self.settings.object_storage_bucket
        if bucket is None:
            raise ObjectStorageNotConfiguredError
        upload_url = str(
            client.generate_presigned_url(
                "put_object",
                Params={
                    "Bucket": bucket,
                    "Key": object_key,
                    "ContentType": content_type,
                    "ContentLength": file_size,
                    "Metadata": {"original-filename": quote(file_name[:180], safe="")},
                },
                ExpiresIn=self.settings.object_storage_upload_expires_seconds,
                HttpMethod="PUT",
            )
        )
        expires_at = datetime.now(UTC) + timedelta(
            seconds=self.settings.object_storage_upload_expires_seconds
        )
        return UploadTicket(
            object_key=object_key,
            upload_url=upload_url,
            public_url=self.media_url(object_key),
            headers={
                "Content-Type": content_type,
                "x-amz-meta-original-filename": quote(file_name[:180], safe=""),
            },
            expires_at=expires_at,
            max_size_bytes=max_size_bytes,
        )

    def expected_home_prefix(self, store_id: UUID) -> str:
        key_prefix = self.settings.object_storage_path_prefix.strip("/")
        return str(PurePosixPath(key_prefix, "stores", str(store_id), "home")) + "/"

    def is_home_object_key(self, store_id: UUID, object_key: str) -> bool:
        return object_key.startswith(self.expected_home_prefix(store_id))

    def expected_product_prefix(self, store_id: UUID) -> str:
        key_prefix = self.settings.object_storage_path_prefix.strip("/")
        return str(PurePosixPath(key_prefix, "stores", str(store_id), "products")) + "/"

    def is_product_object_key(self, store_id: UUID, object_key: str) -> bool:
        return object_key.startswith(self.expected_product_prefix(store_id))

    def expected_product_video_prefix(self, store_id: UUID) -> str:
        key_prefix = self.settings.object_storage_path_prefix.strip("/")
        return (
            str(
                PurePosixPath(key_prefix, "stores", str(store_id), "products", "videos")
            )
            + "/"
        )

    def is_product_video_object_key(self, store_id: UUID, object_key: str) -> bool:
        return object_key.startswith(self.expected_product_video_prefix(store_id))

    def _validate_media(self, content_type: str, file_size: int) -> tuple[str, int]:
        if content_type in ALLOWED_IMAGE_CONTENT_TYPES:
            max_size = self.settings.object_storage_max_image_bytes
            extension = ALLOWED_IMAGE_CONTENT_TYPES[content_type]
        elif content_type in ALLOWED_VIDEO_CONTENT_TYPES:
            max_size = self.settings.object_storage_max_video_bytes
            extension = ALLOWED_VIDEO_CONTENT_TYPES[content_type]
        else:
            raise UnsupportedMediaTypeError
        if file_size > max_size:
            raise MediaFileTooLargeError(max_size)
        return extension, max_size


@lru_cache
def get_object_storage() -> ObjectStorageProvider:
    return ObjectStorageProvider(get_settings())
