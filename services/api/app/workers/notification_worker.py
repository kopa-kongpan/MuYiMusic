from typing import Any, cast

from arq import cron
from arq.connections import RedisSettings
from redis.asyncio import Redis

from app.core.config import get_settings
from app.core.database import get_session_factory
from app.services.notification_delivery_service import NotificationDeliveryService
from app.services.notification_service import NotificationService


async def generate_next_day_reminders(ctx: dict[str, Any]) -> int:
    del ctx
    async with get_session_factory()() as session:
        return await NotificationService(session).generate_next_day_reminders()


async def process_notification_outbox(ctx: dict[str, Any]) -> int:
    redis = cast(Redis, ctx["redis"])
    async with get_session_factory()() as session:
        return await NotificationDeliveryService(
            session, get_settings(), redis
        ).process_pending()


class WorkerSettings:
    settings = get_settings()
    redis_settings = RedisSettings.from_dsn(
        settings.redis_url or "redis://redis:6379/0"
    )
    functions = [generate_next_day_reminders, process_notification_outbox]
    cron_jobs = [
        cron(
            generate_next_day_reminders,
            hour=20,
            minute=0,
            second=0,
            unique=True,
            run_at_startup=True,
        ),
        cron(
            process_notification_outbox, minute=set(range(60)), second=15, unique=True
        ),
    ]
