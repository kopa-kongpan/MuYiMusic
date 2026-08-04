from app.core.config import Settings


def test_local_service_urls_are_built_from_docker_settings() -> None:
    settings = Settings(
        _env_file=None,
        postgres_user="music user",
        postgres_password="password@local",
        postgres_db="music db",
        docker_postgres_port=15432,
        docker_redis_port=16379,
    )

    assert settings.database_url == (
        "postgresql+asyncpg://music%20user:password%40local@localhost:15432/music%20db"
    )
    assert settings.redis_url == "redis://localhost:16379/0"
