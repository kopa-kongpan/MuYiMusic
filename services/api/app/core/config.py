from functools import lru_cache
from urllib.parse import quote

from pydantic import model_validator
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
    postgres_user: str | None = None
    postgres_password: str | None = None
    postgres_db: str | None = None
    docker_postgres_port: int = 15432
    docker_redis_port: int = 16379
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

    @model_validator(mode="after")
    def build_local_service_urls(self) -> "Settings":
        if self.database_url is None and all(
            (self.postgres_user, self.postgres_password, self.postgres_db)
        ):
            user = quote(self.postgres_user or "", safe="")
            password = quote(self.postgres_password or "", safe="")
            database = quote(self.postgres_db or "", safe="")
            self.database_url = (
                f"postgresql+asyncpg://{user}:{password}@localhost:"
                f"{self.docker_postgres_port}/{database}"
            )
        if self.redis_url is None:
            self.redis_url = f"redis://localhost:{self.docker_redis_port}/0"
        return self

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
