from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=("../../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "local"
    database_url: str | None = None
    redis_url: str | None = None
    cors_origins: str = "http://localhost:5173"
    jwt_secret: str | None = None
    jwt_access_token_minutes: int = 480
    admin_initial_username: str = "admin"
    admin_initial_password: str | None = None
    sentry_dsn: str | None = None
    object_storage_provider: str | None = None
    object_storage_endpoint: str | None = None
    object_storage_region: str | None = None
    object_storage_bucket: str | None = None
    object_storage_access_key_id: str | None = None
    object_storage_secret_access_key: str | None = None
    object_storage_session_token: str | None = None
    object_storage_public_base_url: str | None = None
    object_storage_path_prefix: str = "muyimusic"
    object_storage_addressing_style: str = "virtual"
    object_storage_upload_expires_seconds: int = 900
    object_storage_download_expires_seconds: int = 3600
    object_storage_max_image_bytes: int = 10 * 1024 * 1024
    object_storage_max_video_bytes: int = 200 * 1024 * 1024

    def cors_origin_list(self) -> list[str]:
        return [
            origin.strip() for origin in self.cors_origins.split(",") if origin.strip()
        ]

    def has_object_storage_credentials(self) -> bool:
        return all(
            (
                self.object_storage_provider,
                self.object_storage_endpoint,
                self.object_storage_region,
                self.object_storage_bucket,
                self.object_storage_access_key_id,
                self.object_storage_secret_access_key,
            )
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
