from app.core.config import Settings


def test_local_service_urls_are_built_from_docker_settings() -> None:
    """验证 Settings 能从 docker 端口和账号信息拼出本地连接串。

    显式传 database_url=None / redis_url=None：`_env_file=None` 只屏蔽 .env
    文件，不屏蔽真实环境变量。CI 里 DATABASE_URL 是环境变量，不写这两行
    就会被它覆盖，这个用例会失败——而它想测的恰恰是「两者都没给」时的
    拼装逻辑。init 参数在 pydantic-settings 里优先级最高，所以这样能隔离干净。
    """
    settings = Settings(
        _env_file=None,
        database_url=None,
        redis_url=None,
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
