from datetime import UTC, datetime, timedelta
from uuid import UUID

import httpx
from redis.asyncio import Redis
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models.notification import (
    Notification,
    NotificationDeliveryStatus,
    NotificationOutbox,
    NotificationRecipientType,
    NotificationSubscription,
    SubscriptionStatus,
    TeacherAccount,
)
from app.models.user import IdentityProvider, ProviderAccount
from app.providers.wechat_subscribe import (
    WechatSubscribeDeliveryError,
    WechatSubscribeMessage,
    WechatSubscribeNotConfiguredError,
    WechatSubscribeProvider,
)
from app.schemas.notification import (
    NotificationDeliveryListResponse,
    NotificationDeliveryRead,
)


class NotificationDeliveryService:
    max_attempts = 5

    def __init__(self, session: AsyncSession, settings: Settings, redis: Redis) -> None:
        self.session = session
        self.provider = WechatSubscribeProvider(settings, redis)

    async def process_pending(self, limit: int = 50) -> int:
        now = datetime.now(UTC)
        statement = (
            select(NotificationOutbox)
            .where(
                NotificationOutbox.status == NotificationDeliveryStatus.PENDING,
                or_(
                    NotificationOutbox.next_attempt_at.is_(None),
                    NotificationOutbox.next_attempt_at <= now,
                ),
            )
            .order_by(NotificationOutbox.created_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        items = list((await self.session.scalars(statement)).all())
        for item in items:
            await self._deliver(item, now)
        await self.session.commit()
        return len(items)

    async def retry(self, outbox_id: UUID) -> bool:
        item = await self.session.get(NotificationOutbox, outbox_id)
        if item is None:
            return False
        item.status = NotificationDeliveryStatus.PENDING
        item.attempts = 0
        item.next_attempt_at = None
        item.last_error = None
        await self.session.commit()
        return True

    async def list_deliveries(
        self,
        *,
        status: NotificationDeliveryStatus | None,
        page: int,
        page_size: int,
    ) -> NotificationDeliveryListResponse:
        filters = []
        if status is not None:
            filters.append(NotificationOutbox.status == status)
        total = int(
            await self.session.scalar(
                select(func.count(NotificationOutbox.id)).where(*filters)
            )
            or 0
        )
        rows = (
            await self.session.execute(
                select(NotificationOutbox, Notification)
                .join(
                    Notification,
                    Notification.id == NotificationOutbox.notification_id,
                )
                .where(*filters)
                .order_by(NotificationOutbox.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).all()
        return NotificationDeliveryListResponse(
            items=[
                NotificationDeliveryRead(
                    id=outbox.id,
                    notification_id=notification.id,
                    kind=notification.kind,
                    title=notification.title,
                    channel=outbox.channel.value,
                    template_key=outbox.template_key,
                    status=outbox.status,
                    attempts=outbox.attempts,
                    last_error=outbox.last_error,
                    next_attempt_at=outbox.next_attempt_at,
                    sent_at=outbox.sent_at,
                    created_at=outbox.created_at,
                )
                for outbox, notification in rows
            ],
            total=total,
            page=page,
            page_size=page_size,
        )

    async def _deliver(self, item: NotificationOutbox, now: datetime) -> None:
        notification = await self.session.get(Notification, item.notification_id)
        if notification is None:
            self._skip(item, "notification_missing")
            return
        recipient = await self._recipient_user(notification)
        if recipient is None:
            self._skip(item, "recipient_not_bound")
            return
        account = await self.session.scalar(
            select(ProviderAccount).where(
                ProviderAccount.user_id == recipient,
                ProviderAccount.provider == IdentityProvider.WEAPP,
            )
        )
        if account is None:
            self._skip(item, "wechat_account_missing")
            return
        subscription = await self.session.scalar(
            select(NotificationSubscription).where(
                NotificationSubscription.user_id == recipient,
                NotificationSubscription.provider == IdentityProvider.WEAPP.value,
                NotificationSubscription.template_key == item.template_key,
                NotificationSubscription.status == SubscriptionStatus.ACCEPT,
            )
        )
        if subscription is None:
            self._skip(item, "subscription_not_accepted")
            return
        template_id = self.provider.template_id(item.template_key)
        if not template_id:
            self._skip(item, "template_not_configured")
            return
        try:
            data = self.provider.template_data(item.template_key, notification.payload)
            await self.provider.send(
                WechatSubscribeMessage(
                    openid=account.provider_subject,
                    template_id=template_id,
                    page=notification.page_path,
                    data=data,
                )
            )
        except WechatSubscribeNotConfiguredError:
            self._skip(item, "wechat_not_configured")
        except WechatSubscribeDeliveryError as error:
            if not error.retryable:
                self._skip(item, str(error))
                return
            self._retry(item, now, error)
        except httpx.HTTPError as error:
            self._retry(item, now, error)
        else:
            item.status = NotificationDeliveryStatus.SENT
            item.attempts += 1
            item.sent_at = now
            item.next_attempt_at = None
            item.last_error = None

    def _retry(self, item: NotificationOutbox, now: datetime, error: Exception) -> None:
        item.attempts += 1
        item.last_error = str(error)[:2000]
        if item.attempts >= self.max_attempts:
            item.status = NotificationDeliveryStatus.FAILED
            item.next_attempt_at = None
        else:
            item.next_attempt_at = now + timedelta(minutes=min(60, 2**item.attempts))

    async def _recipient_user(self, notification: Notification) -> UUID | None:
        if notification.recipient_type == NotificationRecipientType.USER:
            return notification.recipient_user_id
        if notification.recipient_teacher_id is None:
            return None
        binding = await self.session.scalar(
            select(TeacherAccount).where(
                TeacherAccount.teacher_id == notification.recipient_teacher_id,
                TeacherAccount.provider == IdentityProvider.WEAPP.value,
            )
        )
        return binding.user_id if binding is not None else None

    @staticmethod
    def _skip(item: NotificationOutbox, reason: str) -> None:
        item.status = NotificationDeliveryStatus.SKIPPED
        item.attempts += 1
        item.last_error = reason
        item.next_attempt_at = None
