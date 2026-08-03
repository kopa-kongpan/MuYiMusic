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
    sentry_dsn: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
