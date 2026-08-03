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

    def cors_origin_list(self) -> list[str]:
        return [
            origin.strip() for origin in self.cors_origins.split(",") if origin.strip()
        ]


@lru_cache
def get_settings() -> Settings:
    return Settings()
