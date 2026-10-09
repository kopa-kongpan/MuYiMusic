import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models.payment import Payment, PaymentStatus
from app.models.product import Product, ProductStatus
from app.models.store import StoreStatus
from app.models.user import (
    CourseEntitlement,
    EntitlementStatus,
    Order,
    OrderItem,
    OrderStatus,
    User,
)
from app.providers.wechat_pay import (
    WechatPayAPIError,
    WechatPayNotConfiguredError,
    WechatPayNotification,
    WechatPayOrder,
    WechatPayProvider,
    WechatPaySignatureError,
    WechatPayUnavailableError,
)
from app.repositories.payment_repository import PaymentRepository
from app.repositories.product_repository import ProductRepository
from app.repositories.store_repository import StoreRepository
from app.repositories.user_repository import UserRepository
from app.schemas.order import (
    OrderCreate,
    OrderPaymentStatusResponse,
    WechatPaymentParameters,
)
from app.schemas.user import OrderItemRead, OrderRead

logger = logging.getLogger(__name__)


class PaymentResourceNotFoundError(Exception):
    pass


class InvalidOrderError(Exception):
    pass


class WechatIdentityRequiredError(Exception):
    pass


class PaymentConflictError(Exception):
    pass


class PaymentService:
    PAYMENT_INITIALIZATION_GRACE_SECONDS = 30

    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        provider: WechatPayProvider,
    ) -> None:
        self.session = session
        self.settings = settings
        self.provider = provider
        self.repository = PaymentRepository(session)
        self.user_repository = UserRepository(session)
        self.product_repository = ProductRepository(session)
        self.store_repository = StoreRepository(session)

    async def create_order(
        self,
        *,
        user: User,
        payload: OrderCreate,
        idempotency_key: str,
    ) -> OrderRead:
        existing = await self.user_repository.get_order_by_create_key(
            user.id,
            idempotency_key,
        )
        if existing is not None:
            return await self._order_read(existing)
        store = await self.store_repository.get(payload.store_id)
        if store is None or store.status != StoreStatus.ACTIVE:
            raise InvalidOrderError("门店不存在或已停用")
        now = datetime.now(UTC)
        order = Order(
            order_no=self._order_no(now),
            user_id=user.id,
            store_id=payload.store_id,
            status=OrderStatus.PENDING,
            total_amount_cents=0,
            create_idempotency_key=idempotency_key,
        )
        for requested in payload.items:
            product = await self.product_repository.get_product(requested.product_id)
            if not self._is_purchasable(product, payload.store_id, now):
                raise InvalidOrderError("订单包含不可购买的课程")
            assert product is not None
            sku = next(
                (
                    item
                    for item in product.skus
                    if item.id == requested.sku_id and item.is_active
                ),
                None,
            )
            if sku is None:
                raise InvalidOrderError("所选课程规格已不可购买")
            item_total = sku.price_cents * requested.quantity
            if item_total <= 0:
                raise InvalidOrderError("课程支付金额必须大于零")
            order.total_amount_cents += item_total
            order.items.append(
                OrderItem(
                    product_id=product.id,
                    product_sku_id=sku.id,
                    product_name=product.name,
                    sku_name=sku.name,
                    unit_price_cents=sku.price_cents,
                    quantity=requested.quantity,
                    total_amount_cents=item_total,
                    lesson_count=sku.lesson_count,
                    validity_days=sku.validity_days,
                    product_type=product.product_type,
                )
            )
        try:
            self.session.add(order)
            await self.session.commit()
        except IntegrityError:
            await self.session.rollback()
            existing = await self.user_repository.get_order_by_create_key(
                user.id,
                idempotency_key,
            )
            if existing is None:
                raise
            return await self._order_read(existing)
        return await self._order_read(order)

    async def create_wechat_payment(
        self,
        *,
        user: User,
        order_id: UUID,
    ) -> WechatPaymentParameters:
        order = await self.repository.get_order(
            order_id=order_id,
            user_id=user.id,
            for_update=True,
        )
        if order is None:
            raise PaymentResourceNotFoundError
        if order.status == OrderStatus.CONFIRMED:
            raise PaymentConflictError("订单已经支付")
        if order.status != OrderStatus.PENDING:
            raise PaymentConflictError("当前订单不可支付")
        openid = await self.repository.get_wechat_openid(user.id)
        if openid is None:
            raise WechatIdentityRequiredError
        now = datetime.now(UTC)
        latest = max(order.payments, key=lambda item: item.attempt_no, default=None)
        if (
            latest is not None
            and latest.status == PaymentStatus.PENDING
            and latest.expires_at > now
            and latest.prepay_id
        ):
            return self._payment_parameters(order, latest)
        if latest is not None and latest.status == PaymentStatus.PENDING:
            if (
                latest.prepay_id is None
                and (now - latest.created_at).total_seconds()
                < self.PAYMENT_INITIALIZATION_GRACE_SECONDS
            ):
                raise PaymentConflictError("支付正在初始化，请稍后重试")
            try:
                remote = await self.provider.query_payment(latest.merchant_order_no)
            except WechatPayAPIError as error:
                if error.code != "ORDER_NOT_EXIST":
                    raise
                if latest.expires_at > now and latest.prepay_id is None:
                    return await self._initialize_payment(order, latest, openid)
                latest.status = PaymentStatus.CLOSED
                await self.session.commit()
                remote = None
            if remote is not None and remote.trade_state == "SUCCESS":
                await self.apply_wechat_order(remote)
                raise PaymentConflictError("订单已经支付")
            if remote is not None and remote.trade_state not in {"CLOSED", "REVOKED"}:
                await self.provider.close_payment(latest.merchant_order_no)
            if remote is not None:
                latest.status = PaymentStatus.CLOSED
                await self.session.commit()
        attempt_no = (latest.attempt_no if latest is not None else 0) + 1
        expires_at = now + timedelta(
            minutes=self.settings.wechat_pay_order_expire_minutes
        )
        payment = Payment(
            order=order,
            attempt_no=attempt_no,
            merchant_order_no=f"{order.order_no}{attempt_no:02d}",
            amount_cents=order.total_amount_cents,
            expires_at=expires_at,
        )
        self.session.add(payment)
        await self.session.commit()
        return await self._initialize_payment(order, payment, openid)

    async def _initialize_payment(
        self,
        order: Order,
        payment: Payment,
        openid: str,
    ) -> WechatPaymentParameters:
        try:
            prepay_id = await self.provider.create_jsapi_payment(
                out_trade_no=payment.merchant_order_no,
                description=self._description(order),
                amount_cents=payment.amount_cents,
                openid=openid,
                expires_at=payment.expires_at,
            )
        except WechatPayAPIError as error:
            if error.status_code < 500 and error.code not in {
                "ORDERPAID",
                "SYSTEMERROR",
            }:
                payment.status = PaymentStatus.FAILED
                payment.failure_code = error.code
                await self.session.commit()
            raise
        payment.prepay_id = prepay_id
        payment.failure_code = None
        await self.session.commit()
        return self._payment_parameters(order, payment)

    async def query_order_payment(
        self,
        *,
        user: User,
        order_id: UUID,
    ) -> OrderPaymentStatusResponse:
        order = await self.repository.get_order(order_id=order_id, user_id=user.id)
        if order is None:
            raise PaymentResourceNotFoundError
        latest = max(order.payments, key=lambda item: item.attempt_no, default=None)
        if order.status == OrderStatus.CONFIRMED or latest is None:
            return self._status_response(order, latest)
        if latest.status != PaymentStatus.PENDING:
            return self._status_response(order, latest)
        remote = await self.provider.query_payment(latest.merchant_order_no)
        await self.apply_wechat_order(remote)
        refreshed = await self.repository.get_order(
            order_id=order_id,
            user_id=user.id,
        )
        assert refreshed is not None
        latest = max(refreshed.payments, key=lambda item: item.attempt_no, default=None)
        return self._status_response(refreshed, latest)

    async def handle_notification(
        self,
        notification: WechatPayNotification,
    ) -> None:
        await self.apply_wechat_order(
            notification.order,
            notify_id=notification.notification_id,
        )

    async def apply_wechat_order(
        self,
        remote: WechatPayOrder,
        *,
        notify_id: str | None = None,
    ) -> None:
        payment_reference = await self.repository.get_payment_by_merchant_order_no(
            remote.out_trade_no,
        )
        if payment_reference is None:
            raise PaymentResourceNotFoundError
        order = await self.repository.get_order_by_id_for_update(
            payment_reference.order_id
        )
        if order is None:
            raise PaymentResourceNotFoundError
        payment = await self.repository.get_payment_by_merchant_order_no(
            remote.out_trade_no,
            for_update=True,
        )
        if payment is None:
            raise PaymentResourceNotFoundError
        self._validate_remote(payment, remote)
        if remote.trade_state == "SUCCESS":
            if not remote.transaction_id:
                raise PaymentConflictError("微信支付成功数据缺少交易号")
            if payment.status == PaymentStatus.SUCCEEDED:
                if payment.transaction_id != remote.transaction_id:
                    raise PaymentConflictError("支付交易号与已确认记录不一致")
                await self._close_other_pending_payments(order, payment)
                await self.session.commit()
                return
            paid_at = remote.success_time or datetime.now(UTC)
            payment.status = PaymentStatus.SUCCEEDED
            payment.transaction_id = remote.transaction_id
            payment.paid_at = paid_at
            payment.notify_id = notify_id or payment.notify_id
            if order.status != OrderStatus.CONFIRMED:
                order.status = OrderStatus.CONFIRMED
                await self._grant_entitlements(order, paid_at)
            await self._close_other_pending_payments(order, payment)
        elif remote.trade_state in {"CLOSED", "REVOKED"}:
            payment.status = PaymentStatus.CLOSED
        elif remote.trade_state == "PAYERROR":
            payment.status = PaymentStatus.FAILED
            payment.failure_code = remote.trade_state
        elif remote.trade_state == "REFUND":
            payment.status = PaymentStatus.REFUNDED
        await self.session.commit()

    async def _close_other_pending_payments(
        self,
        order: Order,
        succeeded_payment: Payment,
    ) -> None:
        pending_payments = (
            await self.repository.list_other_pending_payments_for_update(
                order_id=order.id,
                payment_id=succeeded_payment.id,
            )
        )
        for pending in pending_payments:
            try:
                await self.provider.close_payment(pending.merchant_order_no)
            except WechatPayAPIError as error:
                if error.code == "ORDER_NOT_EXIST":
                    pending.status = PaymentStatus.CLOSED
                    continue
                if error.code == "ORDERPAID":
                    await self._record_duplicate_success(pending, order)
                    continue
                logger.error(
                    "failed to close superseded WeChat payment",
                    extra={
                        "order_id": str(order.id),
                        "payment_id": str(pending.id),
                        "wechat_code": error.code,
                    },
                )
            except (
                WechatPayNotConfiguredError,
                WechatPaySignatureError,
                WechatPayUnavailableError,
            ):
                logger.exception(
                    "failed to close superseded WeChat payment",
                    extra={
                        "order_id": str(order.id),
                        "payment_id": str(pending.id),
                    },
                )
            else:
                pending.status = PaymentStatus.CLOSED

    async def _record_duplicate_success(
        self,
        payment: Payment,
        order: Order,
    ) -> None:
        try:
            remote = await self.provider.query_payment(payment.merchant_order_no)
        except (
            WechatPayAPIError,
            WechatPayNotConfiguredError,
            WechatPaySignatureError,
            WechatPayUnavailableError,
        ):
            logger.exception(
                "failed to query potentially duplicated WeChat payment",
                extra={
                    "order_id": str(order.id),
                    "payment_id": str(payment.id),
                },
            )
            return
        self._validate_remote(payment, remote)
        if remote.trade_state != "SUCCESS" or not remote.transaction_id:
            return
        payment.status = PaymentStatus.SUCCEEDED
        payment.transaction_id = remote.transaction_id
        payment.paid_at = remote.success_time or datetime.now(UTC)
        logger.critical(
            "duplicate WeChat payment succeeded and requires reconciliation",
            extra={
                "order_id": str(order.id),
                "payment_id": str(payment.id),
                "transaction_id": remote.transaction_id,
            },
        )

    async def _grant_entitlements(self, order: Order, paid_at: datetime) -> None:
        for item in order.items:
            entitlement = CourseEntitlement(
                user_id=order.user_id,
                store_id=order.store_id,
                order_item_id=item.id,
                product_id=item.product_id,
                product_sku_id=item.product_sku_id,
                course_name=item.product_name,
                product_type=item.product_type,
                total_lessons=item.lesson_count * item.quantity,
                remaining_lessons=item.lesson_count * item.quantity,
                reserved_lessons=0,
                valid_from=paid_at,
                expires_at=paid_at + timedelta(days=item.validity_days),
                status=EntitlementStatus.ACTIVE,
            )
            self.session.add(entitlement)
            if item.product_id is not None:
                await self.session.execute(
                    update(Product)
                    .where(Product.id == item.product_id)
                    .values(sales_count=Product.sales_count + item.quantity)
                )

    def _validate_remote(self, payment: Payment, remote: WechatPayOrder) -> None:
        if (
            remote.app_id != self.settings.wechat_app_id
            or remote.mch_id != self.settings.wechat_pay_mch_id
            or remote.amount_cents != payment.amount_cents
        ):
            raise PaymentConflictError("微信支付订单主体或金额校验失败")

    async def _order_read(self, order: Order) -> OrderRead:
        store = await self.store_repository.get(order.store_id)
        if store is None:
            raise PaymentResourceNotFoundError
        return OrderRead(
            id=order.id,
            order_no=order.order_no,
            user_id=order.user_id,
            store_id=order.store_id,
            store_name=store.name,
            status=order.status,
            total_amount_cents=order.total_amount_cents,
            created_at=order.created_at,
            updated_at=order.updated_at,
            items=[
                OrderItemRead.model_validate(item, from_attributes=True)
                for item in order.items
            ],
        )

    def _payment_parameters(
        self,
        order: Order,
        payment: Payment,
    ) -> WechatPaymentParameters:
        assert payment.prepay_id is not None
        return WechatPaymentParameters(
            order_id=order.id,
            payment_id=payment.id,
            **self.provider.client_parameters(payment.prepay_id),
        )

    @staticmethod
    def _status_response(
        order: Order,
        payment: Payment | None,
    ) -> OrderPaymentStatusResponse:
        return OrderPaymentStatusResponse(
            order_id=order.id,
            order_status=order.status,
            payment_status=payment.status if payment is not None else None,
        )

    @staticmethod
    def _description(order: Order) -> str:
        first = order.items[0].product_name
        return first if len(order.items) == 1 else f"{first}等{len(order.items)}项课程"

    @staticmethod
    def _order_no(now: datetime) -> str:
        return f"O{now:%Y%m%d%H%M%S}{uuid4().hex[:12].upper()}"

    @staticmethod
    def _is_purchasable(
        product: Product | None,
        store_id: UUID,
        now: datetime,
    ) -> bool:
        if (
            product is None
            or product.store_id != store_id
            or product.status != ProductStatus.PUBLISHED
            or not product.category.is_enabled
        ):
            return False
        if product.sale_starts_at is not None and product.sale_starts_at > now:
            return False
        return product.sale_ends_at is None or product.sale_ends_at > now
