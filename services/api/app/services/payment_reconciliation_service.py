import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models.payment import Payment, PaymentStatus
from app.providers.wechat_pay import (
    WechatPayAPIError,
    WechatPayNotConfiguredError,
    WechatPayProvider,
    WechatPaySignatureError,
    WechatPayUnavailableError,
)
from app.repositories.payment_repository import PaymentRepository
from app.services.payment_service import PaymentConflictError, PaymentService

logger = logging.getLogger(__name__)


class PaymentReconciliationService:
    def __init__(
        self, session: AsyncSession, settings: Settings, provider: WechatPayProvider
    ) -> None:
        self.session = session
        self.settings = settings
        self.provider = provider
        self.repository = PaymentRepository(session)
        self.payments = PaymentService(session, settings, provider)

    async def process_pending(self, limit: int = 20) -> int:
        now = datetime.now(UTC)
        candidates = (
            await self.session.execute(
                select(Payment.merchant_order_no, Payment.order_id)
                .where(
                    Payment.status == PaymentStatus.PENDING,
                    Payment.created_at <= now - timedelta(seconds=30),
                    or_(
                        Payment.next_reconcile_at.is_(None),
                        Payment.next_reconcile_at <= now,
                    ),
                )
                .order_by(
                    Payment.next_reconcile_at.asc().nullsfirst(), Payment.created_at
                )
                .limit(limit)
            )
        ).all()
        processed = 0
        for merchant_order_no, order_id in candidates:
            # 与回调、发起支付统一先锁订单，再锁支付单，避免交叉持锁死锁。
            order = await self.repository.get_order_by_id_for_update(
                order_id, skip_locked=True
            )
            if order is None:
                await self.session.commit()
                continue
            payment = await self.repository.get_payment_by_merchant_order_no(
                merchant_order_no, for_update=True
            )
            if (
                payment is None
                or payment.status != PaymentStatus.PENDING
                or (
                    payment.next_reconcile_at is not None
                    and payment.next_reconcile_at > now
                )
            ):
                await self.session.commit()
                continue
            try:
                await self._reconcile(payment, now)
            except (
                WechatPayAPIError,
                WechatPayNotConfiguredError,
                WechatPaySignatureError,
                WechatPayUnavailableError,
                PaymentConflictError,
            ) as error:
                payment.reconcile_attempts += 1
                payment.last_reconcile_error = (
                    error.code
                    if isinstance(error, WechatPayAPIError)
                    else type(error).__name__
                )
                payment.next_reconcile_at = now + timedelta(
                    seconds=min(3600, 60 * 2 ** min(payment.reconcile_attempts, 6))
                )
                logger.warning(
                    "payment reconciliation failed payment_id=%s code=%s",
                    payment.id,
                    payment.last_reconcile_error,
                )
            else:
                payment.reconcile_attempts = 0
                payment.last_reconcile_error = None
                payment.next_reconcile_at = (
                    now + timedelta(minutes=1)
                    if payment.status == PaymentStatus.PENDING
                    else None
                )
            await self.session.commit()
            processed += 1
        return processed

    async def _reconcile(self, payment: Payment, now: datetime) -> None:
        try:
            remote = await self.provider.query_payment(payment.merchant_order_no)
        except WechatPayAPIError as error:
            if error.code != "ORDER_NOT_EXIST":
                raise
            if payment.expires_at <= now:
                payment.status = PaymentStatus.CLOSED
            return
        self.payments._validate_remote(payment, remote)
        if remote.trade_state == "NOTPAY" and payment.expires_at <= now:
            try:
                await self.provider.close_payment(payment.merchant_order_no)
            except WechatPayAPIError as error:
                if error.code == "ORDERPAID":
                    # 查单后刚好付款成功，必须重新查单确认，不能落为已关闭。
                    paid = await self.provider.query_payment(payment.merchant_order_no)
                    if paid.trade_state != "SUCCESS":
                        raise PaymentConflictError("关单时支付状态发生变化") from error
                    await self.payments.apply_wechat_order(paid)
                    return
                if error.code != "ORDER_NOT_EXIST":
                    raise
            payment.status = PaymentStatus.CLOSED
            return
        await self.payments.apply_wechat_order(remote)
