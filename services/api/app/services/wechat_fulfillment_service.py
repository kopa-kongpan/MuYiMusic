import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models.admin import AdminUser
from app.models.payment import Payment, PaymentStatus
from app.models.user import Order, OrderStatus
from app.models.wechat_fulfillment import FulfillmentStatus, WechatFulfillment
from app.providers.wechat_order import (
    WechatOrderAPIError,
    WechatOrderProvider,
    WechatOrderUnavailableError,
    WechatShippingOrder,
)
from app.repositories.audit_repository import AuditRepository
from app.repositories.payment_repository import PaymentRepository
from app.schemas.user import OrderListResponse
from app.schemas.wechat_fulfillment import (
    AdminOrderListResponse,
    AdminOrderRead,
    FulfillmentConfirmRequest,
    FulfillmentRead,
)
from app.services.store_service import can_access_store

logger = logging.getLogger(__name__)


class FulfillmentNotFoundError(Exception):
    pass


class FulfillmentConflictError(Exception):
    pass


class WechatFulfillmentService:
    max_attempts = 8

    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        provider: WechatOrderProvider | None = None,
    ) -> None:
        self.session = session
        self.settings = settings
        self.provider = provider
        self.payments = PaymentRepository(session)

    async def enrich_orders(
        self, response: OrderListResponse
    ) -> AdminOrderListResponse:
        rows = (
            await self.session.execute(
                select(Payment, WechatFulfillment)
                .outerjoin(
                    WechatFulfillment, WechatFulfillment.payment_id == Payment.id
                )
                .where(Payment.order_id.in_([item.id for item in response.items]))
                .order_by(
                    (Payment.status == PaymentStatus.SUCCEEDED).desc(),
                    Payment.attempt_no.desc(),
                )
            )
        ).all()
        by_order: dict[UUID, tuple[Payment, WechatFulfillment | None]] = {}
        for payment, fulfillment in rows:
            by_order.setdefault(payment.order_id, (payment, fulfillment))
        items = []
        for item in response.items:
            pair = by_order.get(item.id)
            items.append(
                AdminOrderRead(
                    **item.model_dump(),
                    wechat_payment_status=pair[0].status if pair else None,
                    fulfillment=FulfillmentRead.model_validate(pair[1])
                    if pair and pair[1]
                    else None,
                )
            )
        return AdminOrderListResponse(
            items=items,
            total=response.total,
            page=response.page,
            page_size=response.page_size,
        )

    async def confirm(
        self,
        *,
        store_id: UUID,
        user_id: UUID,
        order_id: UUID,
        admin: AdminUser,
        payload: FulfillmentConfirmRequest,
    ) -> FulfillmentRead:
        order = await self._admin_order(store_id, user_id, order_id, admin)
        payment = self._succeeded_payment(order)
        existing = await self.session.scalar(
            select(WechatFulfillment)
            .where(WechatFulfillment.payment_id == payment.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if existing:
            if any(
                (
                    existing.logistics_type != payload.logistics_type,
                    existing.item_description != payload.item_description,
                    existing.evidence != payload.evidence,
                )
            ):
                raise FulfillmentConflictError(
                    "该支付单已确认履约，不能重复更改履约信息"
                )
            return FulfillmentRead.model_validate(existing)
        openid = payment.payer_openid or await self.payments.get_wechat_openid(user_id)
        if not openid:
            raise FulfillmentConflictError("支付单缺少微信付款人身份，请先核对交易")
        item = WechatFulfillment(
            payment_id=payment.id,
            confirmed_by_admin_id=admin.id,
            logistics_type=payload.logistics_type,
            item_description=payload.item_description,
            evidence=payload.evidence,
            payer_openid=openid,
            confirmed_at=datetime.now(UTC),
        )
        self.session.add(item)
        await self.session.flush()
        AuditRepository(self.session).add(
            admin_user_id=admin.id,
            action="wechat_fulfillment.confirm",
            resource_type="order",
            resource_id=str(order_id),
            details={"payment_id": str(payment.id), **payload.model_dump()},
        )
        await self.session.commit()
        return FulfillmentRead.model_validate(item)

    async def retry(
        self, *, store_id: UUID, user_id: UUID, order_id: UUID, admin: AdminUser
    ) -> FulfillmentRead:
        order = await self._admin_order(store_id, user_id, order_id, admin)
        payment = self._succeeded_payment(order)
        item = await self.session.scalar(
            select(WechatFulfillment)
            .where(WechatFulfillment.payment_id == payment.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if item is None:
            raise FulfillmentNotFoundError
        if item.status == FulfillmentStatus.SENT:
            return FulfillmentRead.model_validate(item)
        if item.status == FulfillmentStatus.CANCELLED:
            raise FulfillmentConflictError("该履约上报已取消，请核对支付状态")
        item.status = FulfillmentStatus.PENDING
        item.attempts = 0
        item.next_attempt_at = None
        item.last_error = None
        AuditRepository(self.session).add(
            admin_user_id=admin.id,
            action="wechat_fulfillment.retry",
            resource_type="order",
            resource_id=str(order_id),
            details={"payment_id": str(payment.id)},
        )
        await self.session.commit()
        return FulfillmentRead.model_validate(item)

    async def process_pending(self, limit: int = 20) -> int:
        now = datetime.now(UTC)
        refs = (
            await self.session.execute(
                select(
                    WechatFulfillment.id, Payment.order_id, Payment.merchant_order_no
                )
                .join(Payment, Payment.id == WechatFulfillment.payment_id)
                .where(
                    WechatFulfillment.status == FulfillmentStatus.PENDING,
                    or_(
                        WechatFulfillment.next_attempt_at.is_(None),
                        WechatFulfillment.next_attempt_at <= now,
                    ),
                )
                .order_by(
                    WechatFulfillment.next_attempt_at.asc().nullsfirst(),
                    WechatFulfillment.created_at,
                )
                .limit(limit)
            )
        ).all()
        processed = 0
        for fulfillment_id, order_id, merchant_order_no in refs:
            # 全部支付相关操作遵循订单 -> 支付单 -> 履约记录的锁顺序。
            order = await self.payments.get_order_by_id_for_update(
                order_id, skip_locked=True
            )
            if order is None:
                await self.session.commit()
                continue
            payment = await self.payments.get_payment_by_merchant_order_no(
                merchant_order_no, for_update=True
            )
            item = await self.session.scalar(
                select(WechatFulfillment)
                .where(WechatFulfillment.id == fulfillment_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            if (
                item is None
                or item.status != FulfillmentStatus.PENDING
                or (item.next_attempt_at is not None and item.next_attempt_at > now)
            ):
                await self.session.commit()
                continue
            if (
                payment is None
                or payment.status != PaymentStatus.SUCCEEDED
                or (order.status != OrderStatus.CONFIRMED)
            ):
                item.status = FulfillmentStatus.CANCELLED
                item.last_error = "payment_not_succeeded"
                item.next_attempt_at = None
            else:
                await self._deliver(item, payment, now)
            await self.session.commit()
            processed += 1
        return processed

    async def _deliver(
        self, item: WechatFulfillment, payment: Payment, now: datetime
    ) -> None:
        assert self.provider is not None
        item.attempts += 1
        try:
            if not payment.transaction_id:
                raise FulfillmentConflictError("payment_transaction_missing")
            remote = await self.provider.get_order(payment.transaction_id)
            self._validate_remote(item, payment, remote)
            if remote.order_state == 5:
                item.status = FulfillmentStatus.CANCELLED
                item.last_error = "wechat_order_refunded"
                item.next_attempt_at = None
                return
            # 先查询，处理上次微信成功但本地未收到响应/提交的情况。
            # 不盲目重传，避免消耗微信每笔订单唯一的重新发货机会。
            if not remote.delivered:
                await self.provider.upload_shipping(
                    transaction_id=payment.transaction_id,
                    openid=item.payer_openid,
                    logistics_type=item.logistics_type,
                    item_description=item.item_description,
                    confirmed_at=item.confirmed_at,
                )
        except FulfillmentConflictError as error:
            item.status = FulfillmentStatus.FAILED
            item.last_error = str(error)
            item.next_attempt_at = None
        except (WechatOrderAPIError, WechatOrderUnavailableError) as error:
            item.last_error = (
                f"wechat_error_{error.code}"
                if isinstance(error, WechatOrderAPIError)
                else type(error).__name__
            )
            if item.attempts >= self.max_attempts:
                item.status = FulfillmentStatus.FAILED
                item.next_attempt_at = None
            else:
                item.next_attempt_at = now + timedelta(
                    minutes=min(60, 2**item.attempts)
                )
            logger.warning(
                "WeChat fulfillment failed id=%s code=%s", item.id, item.last_error
            )
        else:
            item.status = FulfillmentStatus.SENT
            item.sent_at = now
            item.next_attempt_at = None
            item.last_error = None

    def _validate_remote(
        self, item: WechatFulfillment, payment: Payment, remote: WechatShippingOrder
    ) -> None:
        if (
            remote.transaction_id != payment.transaction_id
            or remote.merchant_id != self.settings.wechat_pay_mch_id
            or remote.merchant_trade_no != payment.merchant_order_no
            or remote.amount_cents != payment.amount_cents
            or remote.openid != item.payer_openid
        ):
            raise FulfillmentConflictError("wechat_order_identity_mismatch")

    async def _admin_order(
        self, store_id: UUID, user_id: UUID, order_id: UUID, admin: AdminUser
    ) -> Order:
        if not can_access_store(admin, store_id):
            raise FulfillmentNotFoundError
        order = await self.payments.get_order_by_id_for_update(order_id)
        if order is None or order.store_id != store_id or order.user_id != user_id:
            raise FulfillmentNotFoundError
        return order

    @staticmethod
    def _succeeded_payment(order: Order) -> Payment:
        payments = [p for p in order.payments if p.status == PaymentStatus.SUCCEEDED]
        if order.status != OrderStatus.CONFIRMED or not payments:
            raise FulfillmentConflictError("仅已支付的微信订单可以确认履约")
        if len(payments) != 1:
            raise FulfillmentConflictError("订单存在重复支付，请先完成退款对账")
        if not payments[0].transaction_id:
            raise FulfillmentConflictError("支付单缺少微信交易号，请先核对交易")
        return payments[0]
