import logging
from typing import Any, cast

from arq import cron
from arq.connections import RedisSettings
from redis.asyncio import Redis

from app.core.config import get_settings
from app.core.database import get_session_factory
from app.core.logging import configure_logging
from app.providers.wechat_order import WechatOrderProvider
from app.providers.wechat_pay import WechatPayProvider
from app.services.notification_delivery_service import NotificationDeliveryService
from app.services.notification_service import NotificationService
from app.services.payment_reconciliation_service import PaymentReconciliationService
from app.services.wechat_fulfillment_service import WechatFulfillmentService


async def startup(ctx: dict[str, Any]) -> None:
    del ctx
    configure_logging()
    # ARQ 自带 handler，避免再传播到应用 root handler 造成日志重复。
    logging.getLogger("arq").propagate = False


async def reconcile_wechat_payments(ctx: dict[str, Any]) -> int:
    del ctx
    settings = get_settings()
    if (
        not settings.wechat_payment_jobs_enabled
        or not settings.has_wechat_pay_credentials()
    ):
        return 0
    async with get_session_factory()() as session:
        return await PaymentReconciliationService(
            session, settings, WechatPayProvider(settings)
        ).process_pending(limit=10)


async def process_wechat_fulfillments(ctx: dict[str, Any]) -> int:
    settings = get_settings()
    if not settings.wechat_payment_jobs_enabled or not all(
        (settings.wechat_app_id, settings.wechat_app_secret, settings.wechat_pay_mch_id)
    ):
        return 0
    redis = cast(Redis, ctx["redis"])
    async with get_session_factory()() as session:
        return await WechatFulfillmentService(
            session, settings, WechatOrderProvider(settings, redis)
        ).process_pending(limit=10)


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
    on_startup = startup
    health_check_interval = 30
    functions = [
        generate_next_day_reminders,
        process_notification_outbox,
        reconcile_wechat_payments,
        process_wechat_fulfillments,
    ]
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
        cron(reconcile_wechat_payments, minute=set(range(60)), second=30, unique=True),
        cron(
            process_wechat_fulfillments, minute=set(range(60)), second=45, unique=True
        ),
    ]
