from collections.abc import AsyncIterator

from redis.asyncio import Redis

from app.core.config import get_settings


async def get_redis() -> AsyncIterator[Redis]:
    client = Redis.from_url(
        get_settings().redis_url or "redis://redis:6379/0",
    )
    try:
        yield client
    finally:
        await client.aclose()
