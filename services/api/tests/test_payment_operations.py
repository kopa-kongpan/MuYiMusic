import base64
import json
import time
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

import app.api.dependencies as dependencies
import app.api.v1.admin.users as users_api
import app.api.v1.app.orders as orders_api
from app.core.config import Settings
from app.core.security import create_access_token
from app.main import app
from app.models.audit import AuditLog
from app.models.payment import Payment, PaymentStatus
from app.models.product import Product, ProductSku
from app.models.store import Store
from app.models.user import (
    CourseEntitlement,
    IdentityProvider,
    Order,
    OrderItem,
    OrderStatus,
    ProviderAccount,
    User,
)
from app.models.wechat_fulfillment import FulfillmentStatus, WechatFulfillment
from app.providers.wechat_order import (
    WechatOrderUnavailableError,
    WechatShippingOrder,
)
from app.providers.wechat_pay import (
    WechatPayAPIError,
    WechatPayOrder,
    WechatPayProvider,
    WechatPayUnavailableError,
    get_wechat_pay_provider,
)
from app.schemas.wechat_fulfillment import FulfillmentConfirmRequest
from app.services.payment_reconciliation_service import PaymentReconciliationService
from app.services.payment_service import PaymentService
from app.services.wechat_fulfillment_service import WechatFulfillmentService
from tests.conftest import api_context, make_admin, make_product, make_store

pytestmark = pytest.mark.asyncio


def settings() -> Settings:
    return Settings(
        _env_file=None,
        app_env="local",
        wechat_app_id="wx-payment-operations",
        wechat_pay_mch_id="1234567890",
        jwt_secret="payment-operations-test-secret-at-least-32-bytes",
    )


@dataclass
class PaymentWorld:
    store: Store
    user: User
    product: Product
    order: Order
    payment: Payment


async def build_world(
    session: AsyncSession, *, paid: bool = False, expired: bool = False
) -> PaymentWorld:
    now = datetime.now(UTC)
    store = make_store(f"支付运维-{uuid4().hex[:8]}")
    session.add(store)
    await session.flush()
    product = make_product(store)
    sku = ProductSku(
        product=product,
        name="2课时",
        price_cents=9800,
        lesson_count=2,
        validity_days=90,
    )
    user = User(nickname="支付运维学员")
    openid = f"openid-{uuid4().hex}"
    user.provider_accounts.append(
        ProviderAccount(
            provider=IdentityProvider.WEAPP,
            provider_subject=openid,
        )
    )
    session.add_all([product, sku, user])
    await session.flush()
    order = Order(
        order_no=f"O{uuid4().hex[:20]}",
        user_id=user.id,
        store_id=store.id,
        status=OrderStatus.CONFIRMED if paid else OrderStatus.PENDING,
        total_amount_cents=9800,
    )
    order.items.append(
        OrderItem(
            product_id=product.id,
            product_sku_id=sku.id,
            product_name=product.name,
            sku_name=sku.name,
            unit_price_cents=9800,
            quantity=1,
            total_amount_cents=9800,
            lesson_count=2,
            validity_days=90,
            product_type=product.product_type,
        )
    )
    payment = Payment(
        order=order,
        attempt_no=1,
        merchant_order_no=f"{order.order_no}01",
        amount_cents=9800,
        prepay_id="test-prepay",
        payer_openid=openid,
        transaction_id=f"T{uuid4().hex}" if paid else None,
        status=PaymentStatus.SUCCEEDED if paid else PaymentStatus.PENDING,
        created_at=now - timedelta(minutes=2),
        expires_at=now + timedelta(minutes=-1 if expired else 30),
    )
    session.add(payment)
    await session.commit()
    return PaymentWorld(store, user, product, order, payment)


def remote_payment(payment: Payment, state: str) -> WechatPayOrder:
    return WechatPayOrder(
        out_trade_no=payment.merchant_order_no,
        transaction_id=f"T{payment.id.hex}" if state == "SUCCESS" else None,
        trade_state=state,
        amount_cents=payment.amount_cents,
        app_id=settings().wechat_app_id or "",
        mch_id=settings().wechat_pay_mch_id or "",
        success_time=datetime.now(UTC) if state == "SUCCESS" else None,
    )


class FakePay(WechatPayProvider):
    def __init__(self) -> None:
        super().__init__(settings())
        self.orders: dict[str, WechatPayOrder | Exception] = {}
        self.closed: list[str] = []
        self.queries: list[str] = []
        self.close_race: WechatPayOrder | None = None

    async def query_payment(self, out_trade_no: str) -> WechatPayOrder:
        self.queries.append(out_trade_no)
        result = self.orders[out_trade_no]
        if isinstance(result, Exception):
            raise result
        return result

    async def close_payment(self, out_trade_no: str) -> None:
        self.closed.append(out_trade_no)
        if self.close_race:
            self.orders[out_trade_no] = self.close_race
            raise WechatPayAPIError("ORDERPAID", "paid", 400)


async def test_lost_callback_is_recovered_without_duplicate_entitlements() -> None:
    async with api_context() as ctx:
        world = await build_world(ctx.session)
        fake = FakePay()
        remote = remote_payment(world.payment, "SUCCESS")
        fake.orders[world.payment.merchant_order_no] = remote
        service = PaymentReconciliationService(ctx.session, settings(), fake)
        assert await service.process_pending() == 1
        assert await service.process_pending() == 0
        await PaymentService(ctx.session, settings(), fake).apply_wechat_order(remote)
        assert world.payment.status == PaymentStatus.SUCCEEDED
        assert world.order.status == OrderStatus.CONFIRMED
        entitlements = list(
            (
                await ctx.session.scalars(
                    select(CourseEntitlement).where(
                        CourseEntitlement.order_item_id == world.order.items[0].id
                    )
                )
            ).all()
        )
        assert len(entitlements) == 1
        assert entitlements[0].remaining_lessons == 2
        await ctx.session.refresh(world.product)
        assert world.product.sales_count == 1
        assert await ctx.session.scalar(select(func.count(WechatFulfillment.id))) == 0


@pytest.mark.parametrize("exists", [True, False])
async def test_expired_payment_is_closed_only_after_wechat_query(exists: bool) -> None:
    async with api_context() as ctx:
        world = await build_world(ctx.session, expired=True)
        fake = FakePay()
        fake.orders[world.payment.merchant_order_no] = (
            remote_payment(world.payment, "NOTPAY")
            if exists
            else WechatPayAPIError("ORDER_NOT_EXIST", "missing", 404)
        )
        await PaymentReconciliationService(
            ctx.session, settings(), fake
        ).process_pending()
        assert fake.queries == [world.payment.merchant_order_no]
        assert fake.closed == ([world.payment.merchant_order_no] if exists else [])
        assert world.payment.status == PaymentStatus.CLOSED
        assert world.order.status == OrderStatus.PENDING


@pytest.mark.parametrize("state", ["NOTPAY", "USERPAYING", "ORDER_NOT_EXIST"])
async def test_unexpired_or_processing_payments_remain_payable(state: str) -> None:
    async with api_context() as ctx:
        world = await build_world(ctx.session, expired=state == "USERPAYING")
        fake = FakePay()
        fake.orders[world.payment.merchant_order_no] = (
            WechatPayAPIError(state, "missing", 404)
            if state == "ORDER_NOT_EXIST"
            else remote_payment(world.payment, state)
        )
        await PaymentReconciliationService(
            ctx.session, settings(), fake
        ).process_pending()
        assert world.payment.status == PaymentStatus.PENDING
        assert world.payment.next_reconcile_at is not None
        assert not fake.closed


async def test_payment_during_close_is_confirmed_instead_of_closed() -> None:
    async with api_context() as ctx:
        world = await build_world(ctx.session, expired=True)
        fake = FakePay()
        fake.orders[world.payment.merchant_order_no] = remote_payment(
            world.payment, "NOTPAY"
        )
        fake.close_race = remote_payment(world.payment, "SUCCESS")
        await PaymentReconciliationService(
            ctx.session, settings(), fake
        ).process_pending()
        assert world.payment.status == PaymentStatus.SUCCEEDED
        assert world.order.status == OrderStatus.CONFIRMED
        assert len(fake.queries) == 2


async def test_failed_query_backs_off_and_does_not_block_other_payments() -> None:
    async with api_context() as ctx:
        failing = await build_world(ctx.session)
        success = await build_world(ctx.session)
        fake = FakePay()
        fake.orders[failing.payment.merchant_order_no] = WechatPayUnavailableError(
            "timeout"
        )
        fake.orders[success.payment.merchant_order_no] = remote_payment(
            success.payment, "SUCCESS"
        )
        service = PaymentReconciliationService(ctx.session, settings(), fake)
        assert await service.process_pending() == 2
        assert failing.payment.status == PaymentStatus.PENDING
        assert failing.payment.reconcile_attempts == 1
        assert failing.payment.next_reconcile_at > datetime.now(UTC)
        assert success.payment.status == PaymentStatus.SUCCEEDED
        assert await service.process_pending() == 0


@pytest.mark.parametrize(
    "local,remote_state",
    [
        (PaymentStatus.REFUNDED, "SUCCESS"),
        (PaymentStatus.SUCCEEDED, "CLOSED"),
    ],
)
async def test_delayed_results_cannot_regress_paid_or_refunded_status(
    local: PaymentStatus, remote_state: str
) -> None:
    async with api_context() as ctx:
        world = await build_world(ctx.session, paid=True)
        world.payment.status = local
        await ctx.session.commit()
        await PaymentService(ctx.session, settings(), FakePay()).apply_wechat_order(
            remote_payment(world.payment, remote_state)
        )
        assert world.payment.status == local


async def test_paid_payment_can_still_transition_to_refunded_on_query() -> None:
    async with api_context() as ctx:
        world = await build_world(ctx.session, paid=True)
        await PaymentService(ctx.session, settings(), FakePay()).apply_wechat_order(
            remote_payment(world.payment, "REFUND")
        )
        assert world.payment.status == PaymentStatus.REFUNDED


class FakeShipping:
    def __init__(self, payment: Payment) -> None:
        self.remote = WechatShippingOrder(
            transaction_id=payment.transaction_id or "",
            merchant_id="1234567890",
            merchant_trade_no=payment.merchant_order_no,
            amount_cents=payment.amount_cents,
            openid=payment.payer_openid or "",
            order_state=1,
            delivered=False,
        )
        self.uploads: list[dict[str, Any]] = []
        self.timeout_after_delivery = False
        self.error: Exception | None = None
        self.queries = 0

    async def get_order(self, transaction_id: str) -> WechatShippingOrder:
        self.queries += 1
        if self.error:
            raise self.error
        assert transaction_id == self.remote.transaction_id
        return self.remote

    async def upload_shipping(self, **kwargs: Any) -> None:
        self.uploads.append(kwargs)
        self.remote = replace(self.remote, delivered=True, order_state=2)
        if self.timeout_after_delivery:
            raise WechatOrderUnavailableError("timeout")


def confirm_payload() -> FulfillmentConfirmRequest:
    return FulfillmentConfirmRequest(
        logistics_type=3,
        item_description="钢琴课服务已按约定交付",
        evidence="已核对课程履约记录并由门店确认",
    )


async def confirm_world(ctx: Any, world: PaymentWorld) -> WechatFulfillment:
    admin = await make_admin(
        ctx.session, permission_codes=("consumptions:manage",), stores=(world.store,)
    )
    service = WechatFulfillmentService(ctx.session, settings())
    kwargs = dict(
        store_id=world.store.id,
        user_id=world.user.id,
        order_id=world.order.id,
        admin=admin,
        payload=confirm_payload(),
    )
    first = await service.confirm(**kwargs)
    second = await service.confirm(**kwargs)
    assert first.id == second.id
    item = await ctx.session.get(WechatFulfillment, first.id)
    assert item is not None
    return item


async def test_fulfillment_requires_admin_confirmation_and_is_sent_once() -> None:
    async with api_context() as ctx:
        world = await build_world(ctx.session, paid=True)
        item = await confirm_world(ctx, world)
        assert item.status == FulfillmentStatus.PENDING
        assert (
            await ctx.session.scalar(
                select(func.count(AuditLog.id)).where(
                    AuditLog.action == "wechat_fulfillment.confirm"
                )
            )
            == 1
        )
        fake = FakeShipping(world.payment)
        service = WechatFulfillmentService(ctx.session, settings(), fake)
        assert await service.process_pending() == 1
        assert await service.process_pending() == 0
        assert item.status == FulfillmentStatus.SENT
        assert len(fake.uploads) == 1
        assert fake.uploads[0]["logistics_type"] == 3
        assert item.sent_at is not None


async def test_ambiguous_fulfillment_timeout_checks_remote_before_retry() -> None:
    async with api_context() as ctx:
        world = await build_world(ctx.session, paid=True)
        item = await confirm_world(ctx, world)
        fake = FakeShipping(world.payment)
        fake.timeout_after_delivery = True
        service = WechatFulfillmentService(ctx.session, settings(), fake)
        await service.process_pending()
        assert item.status == FulfillmentStatus.PENDING
        assert item.next_attempt_at > datetime.now(UTC)
        assert await service.process_pending() == 0
        item.next_attempt_at = datetime.now(UTC) - timedelta(seconds=1)
        await ctx.session.commit()
        await service.process_pending()
        assert item.status == FulfillmentStatus.SENT
        assert len(fake.uploads) == 1
        assert fake.queries == 2


@pytest.mark.parametrize("remote_refund", [False, True])
async def test_refunded_payment_is_never_uploaded(remote_refund: bool) -> None:
    async with api_context() as ctx:
        world = await build_world(ctx.session, paid=True)
        item = await confirm_world(ctx, world)
        fake = FakeShipping(world.payment)
        if remote_refund:
            fake.remote = replace(fake.remote, order_state=5)
        else:
            world.payment.status = PaymentStatus.REFUNDED
            await ctx.session.commit()
        await WechatFulfillmentService(ctx.session, settings(), fake).process_pending()
        assert item.status == FulfillmentStatus.CANCELLED
        assert not fake.uploads


async def test_shipping_identity_mismatch_fails_without_uploading() -> None:
    async with api_context() as ctx:
        world = await build_world(ctx.session, paid=True)
        item = await confirm_world(ctx, world)
        fake = FakeShipping(world.payment)
        fake.remote = replace(fake.remote, openid="another-user")
        await WechatFulfillmentService(ctx.session, settings(), fake).process_pending()
        assert item.status == FulfillmentStatus.FAILED
        assert item.last_error == "wechat_order_identity_mismatch"
        assert not fake.uploads


async def test_fulfillment_gives_up_then_can_be_retried_by_authorized_admin() -> None:
    async with api_context() as ctx:
        world = await build_world(ctx.session, paid=True)
        item = await confirm_world(ctx, world)
        item.attempts = 7
        await ctx.session.commit()
        fake = FakeShipping(world.payment)
        fake.error = WechatOrderUnavailableError("unavailable")
        service = WechatFulfillmentService(ctx.session, settings(), fake)
        await service.process_pending()
        assert item.status == FulfillmentStatus.FAILED
        assert item.next_attempt_at is None
        admin = await make_admin(
            ctx.session,
            permission_codes=("consumptions:manage",),
            stores=(world.store,),
        )
        await service.retry(
            store_id=world.store.id,
            user_id=world.user.id,
            order_id=world.order.id,
            admin=admin,
        )
        fake.error = None
        await service.process_pending()
        assert item.status == FulfillmentStatus.SENT
        assert item.attempts == 1


@pytest.mark.parametrize(
    "scope,expected",
    [
        ("allowed", 200),
        ("other-store", 404),
        ("read-only", 403),
        ("unpaid", 409),
    ],
)
async def test_fulfillment_api_enforces_payment_permission_and_store_scope(
    monkeypatch: pytest.MonkeyPatch, scope: str, expected: int
) -> None:
    s = settings()
    monkeypatch.setattr(dependencies, "get_settings", lambda: s)
    monkeypatch.setattr(users_api, "get_settings", lambda: s)
    async with api_context() as ctx:
        world = await build_world(ctx.session, paid=scope != "unpaid")
        other = make_store(f"其他履约门店-{uuid4().hex[:8]}")
        ctx.session.add(other)
        await ctx.session.flush()
        admin = await make_admin(
            ctx.session,
            permission_codes=("users:read",)
            if scope == "read-only"
            else ("users:read", "consumptions:manage"),
            stores=(other,) if scope == "other-store" else (world.store,),
        )
        auth = {
            "Authorization": "Bearer "
            + create_access_token(
                admin.id, s.jwt_secret or "", 60, subject_type="admin"
            )
        }
        url = f"/api/v1/admin/stores/{world.store.id}/users/{world.user.id}/orders"
        response = await ctx.client.post(
            f"{url}/{world.order.id}/wechat-fulfillment",
            headers=auth,
            json=confirm_payload().model_dump(),
        )
        assert response.status_code == expected, response.text
        if expected == 200:
            listing = await ctx.client.get(url, headers=auth)
            assert listing.status_code == 200, listing.text
            row = listing.json()["items"][0]
            assert row["wechat_payment_status"] == "succeeded"
            assert row["fulfillment"]["status"] == "pending"
            assert "payer_openid" not in listing.text
            duplicate = await ctx.client.post(
                f"{url}/{world.order.id}/wechat-fulfillment",
                headers=auth,
                json={**confirm_payload().model_dump(), "evidence": "不同的履约说明"},
            )
            assert duplicate.status_code == 409


async def test_signed_encrypted_callback_through_fulfillment_pipeline(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    wechat_private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_path = tmp_path / "wechat-public.pem"
    public_path.write_bytes(
        wechat_private.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )
    s = settings().model_copy(
        update={
            "wechat_pay_api_v3_key": "0123456789abcdef0123456789abcdef",
            "wechat_pay_public_key_id": "PUB_KEY_ID_PIPELINE_TEST",
            "wechat_pay_public_key_path": str(public_path),
        }
    )
    monkeypatch.setattr(orders_api, "get_settings", lambda: s)
    async with api_context() as ctx:
        world = await build_world(ctx.session)
        app.dependency_overrides[get_wechat_pay_provider] = lambda: WechatPayProvider(s)
        resource = {
            "appid": s.wechat_app_id,
            "mchid": s.wechat_pay_mch_id,
            "out_trade_no": world.payment.merchant_order_no,
            "transaction_id": f"T{world.payment.id.hex}",
            "trade_state": "SUCCESS",
            "success_time": datetime.now(UTC).isoformat(),
            "amount": {"total": 9800, "currency": "CNY"},
        }
        nonce = "nonce-123456"
        ciphertext = AESGCM(s.wechat_pay_api_v3_key.encode()).encrypt(
            nonce.encode(),
            json.dumps(resource).encode(),
            b"transaction",
        )
        body = json.dumps(
            {
                "id": f"notification-{uuid4().hex}",
                "event_type": "TRANSACTION.SUCCESS",
                "resource": {
                    "algorithm": "AEAD_AES_256_GCM",
                    "nonce": nonce,
                    "associated_data": "transaction",
                    "ciphertext": base64.b64encode(ciphertext).decode(),
                },
            }
        ).encode()
        timestamp = str(int(time.time()))
        message = f"{timestamp}\nsignature-nonce\n{body.decode()}\n".encode()
        signature = wechat_private.sign(message, padding.PKCS1v15(), hashes.SHA256())
        headers = {
            "Wechatpay-Timestamp": timestamp,
            "Wechatpay-Nonce": "signature-nonce",
            "Wechatpay-Signature": base64.b64encode(signature).decode(),
            "Wechatpay-Serial": s.wechat_pay_public_key_id,
        }
        url = "/api/v1/webhooks/wechat-pay"
        invalid = await ctx.client.post(url, content=body + b" ", headers=headers)
        assert invalid.status_code == 401
        for _ in range(2):
            response = await ctx.client.post(url, content=body, headers=headers)
            assert response.status_code == 200, response.text
        await ctx.session.refresh(world.payment)
        await ctx.session.refresh(world.order)
        assert world.order.status == OrderStatus.CONFIRMED
        assert world.payment.status == PaymentStatus.SUCCEEDED
        assert (
            await ctx.session.scalar(
                select(func.count(CourseEntitlement.id)).where(
                    CourseEntitlement.order_item_id == world.order.items[0].id
                )
            )
            == 1
        )
        assert await ctx.session.scalar(select(func.count(WechatFulfillment.id))) == 0
        item = await confirm_world(ctx, world)
        fake = FakeShipping(world.payment)
        await WechatFulfillmentService(ctx.session, s, fake).process_pending()
        assert item.status == FulfillmentStatus.SENT
        assert len(fake.uploads) == 1
