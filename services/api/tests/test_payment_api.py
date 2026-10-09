import base64
import json
import time
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import httpx
import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy import func, select

import app.api.dependencies as api_dependencies
import app.api.v1.app.orders as orders_api
from app.core.config import Settings
from app.core.security import create_access_token
from app.main import app
from app.models.payment import Payment, PaymentStatus
from app.models.product import ProductSku
from app.models.user import (
    CourseEntitlement,
    IdentityProvider,
    Order,
    OrderStatus,
    ProviderAccount,
    User,
)
from app.providers.wechat_pay import (
    WechatPayAPIError,
    WechatPayNotification,
    WechatPayOrder,
    WechatPayProvider,
    WechatPayUnavailableError,
    get_wechat_pay_provider,
)
from tests.conftest import api_context, make_product, make_store

pytestmark = pytest.mark.asyncio

APP_ID = "wx30ebb435bb61ba6b"
MCH_ID = "1750778977"
JWT_SECRET = "payment-test-jwt-secret-2026-at-least-32-bytes"


class FakeWechatPayProvider:
    def __init__(self) -> None:
        self.created: list[dict[str, Any]] = []
        self.closed: list[str] = []
        self.remote_order: WechatPayOrder | None = None
        self.create_error: Exception | None = None
        self.query_error: Exception | None = None

    async def create_jsapi_payment(self, **kwargs: Any) -> str:
        self.created.append(kwargs)
        if self.create_error is not None:
            raise self.create_error
        return "wx-test-prepay-id"

    async def query_payment(self, out_trade_no: str) -> WechatPayOrder:
        if self.query_error is not None:
            raise self.query_error
        assert self.remote_order is not None
        assert self.remote_order.out_trade_no == out_trade_no
        return self.remote_order

    async def close_payment(self, out_trade_no: str) -> None:
        self.closed.append(out_trade_no)

    def client_parameters(self, prepay_id: str) -> dict[str, str]:
        assert prepay_id == "wx-test-prepay-id"
        return {
            "timeStamp": "1791475200",
            "nonceStr": "test-payment-nonce",
            "package": f"prepay_id={prepay_id}",
            "signType": "RSA",
            "paySign": "test-payment-signature",
        }

    def parse_notification(
        self,
        headers: httpx.Headers,
        body: bytes,
    ) -> WechatPayNotification:
        assert headers.get("Wechatpay-Serial") == "TEST_PUBLIC_KEY_ID"
        assert body == b"{}"
        assert self.remote_order is not None
        return WechatPayNotification(
            notification_id="notification-payment-test",
            event_type="TRANSACTION.SUCCESS",
            order=self.remote_order,
        )


async def test_order_payment_notification_is_idempotent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings(
        _env_file=None,
        app_env="local",
        jwt_secret=JWT_SECRET,
        wechat_app_id=APP_ID,
        wechat_pay_mch_id=MCH_ID,
    )
    fake = FakeWechatPayProvider()
    monkeypatch.setattr(api_dependencies, "get_settings", lambda: settings)
    monkeypatch.setattr(orders_api, "get_settings", lambda: settings)

    async with api_context() as context:
        app.dependency_overrides[get_wechat_pay_provider] = lambda: fake
        store = make_store(f"支付门店-{uuid4().hex[:8]}")
        context.session.add(store)
        await context.session.flush()
        product = make_product(store, name="微信支付钢琴课")
        sku = ProductSku(
            product=product,
            name="8课时",
            price_cents=12800,
            lesson_count=8,
            validity_days=180,
        )
        user = User(nickname="微信支付学员")
        user.provider_accounts.append(
            ProviderAccount(
                provider=IdentityProvider.WEAPP,
                provider_subject="wechat-openid-payment-test",
            )
        )
        context.session.add_all((product, sku, user))
        await context.session.flush()
        token = create_access_token(
            user.id,
            JWT_SECRET,
            60,
            subject_type="user",
        )
        headers = {
            "Authorization": f"Bearer {token}",
            "Idempotency-Key": "payment-order-test-key",
        }
        payload = {
            "store_id": str(store.id),
            "items": [
                {
                    "product_id": str(product.id),
                    "sku_id": str(sku.id),
                    "quantity": 2,
                }
            ],
        }
        first = await context.client.post(
            "/api/v1/app/orders",
            headers=headers,
            json=payload,
        )
        second = await context.client.post(
            "/api/v1/app/orders",
            headers=headers,
            json=payload,
        )
        assert first.status_code == 201, first.text
        assert second.status_code == 201, second.text
        assert first.json()["id"] == second.json()["id"]
        assert first.json()["total_amount_cents"] == 25600
        order_id = first.json()["id"]

        payment_response = await context.client.post(
            f"/api/v1/app/orders/{order_id}/payments/wechat",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert payment_response.status_code == 200, payment_response.text
        assert payment_response.json()["package"] == "prepay_id=wx-test-prepay-id"
        assert fake.created[0]["amount_cents"] == 25600
        assert fake.created[0]["openid"] == "wechat-openid-payment-test"

        payment = await context.session.scalar(
            select(Payment).where(Payment.order_id == order_id)
        )
        assert payment is not None
        fake.remote_order = WechatPayOrder(
            out_trade_no=payment.merchant_order_no,
            transaction_id="4200000000000000000000000001",
            trade_state="SUCCESS",
            amount_cents=25600,
            app_id=APP_ID,
            mch_id=MCH_ID,
            success_time=datetime.now(UTC),
        )
        webhook_headers = {"Wechatpay-Serial": "TEST_PUBLIC_KEY_ID"}
        first_webhook = await context.client.post(
            "/api/v1/webhooks/wechat-pay",
            headers=webhook_headers,
            content=b"{}",
        )
        second_webhook = await context.client.post(
            "/api/v1/webhooks/wechat-pay",
            headers=webhook_headers,
            content=b"{}",
        )
        assert first_webhook.status_code == 200, first_webhook.text
        assert second_webhook.status_code == 200, second_webhook.text

        order = await context.session.get(Order, order_id)
        assert order is not None
        await context.session.refresh(order)
        await context.session.refresh(payment)
        await context.session.refresh(product)
        assert order.status == OrderStatus.CONFIRMED
        assert payment.status == PaymentStatus.SUCCEEDED
        assert payment.transaction_id == "4200000000000000000000000001"
        assert product.sales_count == 2
        entitlements = int(
            await context.session.scalar(
                select(func.count(CourseEntitlement.id)).where(
                    CourseEntitlement.order_item_id == order.items[0].id
                )
            )
            or 0
        )
        assert entitlements == 1
        entitlement = await context.session.scalar(
            select(CourseEntitlement).where(
                CourseEntitlement.order_item_id == order.items[0].id
            )
        )
        assert entitlement is not None
        assert entitlement.total_lessons == 16
        assert entitlement.remaining_lessons == 16


async def test_wechat_notification_signature_and_decryption(tmp_path: Any) -> None:
    merchant_private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    wechat_private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_path = tmp_path / "merchant_private.pem"
    public_path = tmp_path / "wechat_public.pem"
    private_path.write_bytes(
        merchant_private.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    public_path.write_bytes(
        wechat_private.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )
    api_v3_key = "12345678901234567890123456789012"
    settings = Settings(
        _env_file=None,
        wechat_app_id=APP_ID,
        wechat_pay_mch_id=MCH_ID,
        wechat_pay_merchant_serial_no="MERCHANT_SERIAL",
        wechat_pay_api_v3_key=api_v3_key,
        wechat_pay_private_key_path=str(private_path),
        wechat_pay_public_key_id="PUB_KEY_ID_TEST",
        wechat_pay_public_key_path=str(public_path),
        wechat_pay_notify_url="https://muyimusic.net/api/v1/webhooks/wechat-pay",
    )
    provider = WechatPayProvider(settings)
    resource_payload = {
        "appid": APP_ID,
        "mchid": MCH_ID,
        "out_trade_no": "O20261009000000TEST0000000001",
        "transaction_id": "4200000000000000000000000002",
        "trade_state": "SUCCESS",
        "success_time": "2026-10-09T12:00:00+08:00",
        "amount": {"total": 9900, "currency": "CNY"},
    }
    nonce = b"paymenttest"
    associated_data = b"transaction"
    ciphertext = AESGCM(api_v3_key.encode()).encrypt(
        nonce,
        json.dumps(resource_payload, separators=(",", ":")).encode(),
        associated_data,
    )
    envelope = {
        "id": "notification-crypto-test",
        "event_type": "TRANSACTION.SUCCESS",
        "resource": {
            "algorithm": "AEAD_AES_256_GCM",
            "ciphertext": base64.b64encode(ciphertext).decode(),
            "nonce": nonce.decode(),
            "associated_data": associated_data.decode(),
        },
    }
    body = json.dumps(envelope, separators=(",", ":")).encode()
    timestamp = str(int(time.time()))
    signature_nonce = "signature-nonce"
    message = f"{timestamp}\n{signature_nonce}\n{body.decode()}\n".encode()
    signature = wechat_private.sign(message, padding.PKCS1v15(), hashes.SHA256())
    notification = provider.parse_notification(
        httpx.Headers(
            {
                "Wechatpay-Timestamp": timestamp,
                "Wechatpay-Nonce": signature_nonce,
                "Wechatpay-Signature": base64.b64encode(signature).decode(),
                "Wechatpay-Serial": "PUB_KEY_ID_TEST",
            }
        ),
        body,
    )
    assert notification.notification_id == "notification-crypto-test"
    assert notification.order.out_trade_no == resource_payload["out_trade_no"]
    assert notification.order.amount_cents == 9900


async def test_payment_recovers_after_ambiguous_create_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings(
        _env_file=None,
        app_env="local",
        jwt_secret=JWT_SECRET,
        wechat_app_id=APP_ID,
        wechat_pay_mch_id=MCH_ID,
    )
    fake = FakeWechatPayProvider()
    fake.create_error = WechatPayUnavailableError("timeout")
    monkeypatch.setattr(api_dependencies, "get_settings", lambda: settings)
    monkeypatch.setattr(orders_api, "get_settings", lambda: settings)

    async with api_context() as context:
        app.dependency_overrides[get_wechat_pay_provider] = lambda: fake
        store = make_store(f"支付恢复门店-{uuid4().hex[:8]}")
        context.session.add(store)
        await context.session.flush()
        product = make_product(store, name="微信支付恢复课程")
        sku = ProductSku(
            product=product,
            name="单课时",
            price_cents=9900,
            lesson_count=1,
            validity_days=30,
        )
        user = User(nickname="支付恢复学员")
        user.provider_accounts.append(
            ProviderAccount(
                provider=IdentityProvider.WEAPP,
                provider_subject="wechat-openid-payment-recovery",
            )
        )
        context.session.add_all((product, sku, user))
        await context.session.flush()
        token = create_access_token(
            user.id,
            JWT_SECRET,
            60,
            subject_type="user",
        )
        auth = {"Authorization": f"Bearer {token}"}
        order_response = await context.client.post(
            "/api/v1/app/orders",
            headers={**auth, "Idempotency-Key": "payment-recovery-order-key"},
            json={
                "store_id": str(store.id),
                "items": [
                    {
                        "product_id": str(product.id),
                        "sku_id": str(sku.id),
                        "quantity": 1,
                    }
                ],
            },
        )
        assert order_response.status_code == 201, order_response.text
        order_id = order_response.json()["id"]

        first = await context.client.post(
            f"/api/v1/app/orders/{order_id}/payments/wechat",
            headers=auth,
        )
        assert first.status_code == 502, first.text
        initializing = await context.client.post(
            f"/api/v1/app/orders/{order_id}/payments/wechat",
            headers=auth,
        )
        assert initializing.status_code == 409, initializing.text

        payment = await context.session.scalar(
            select(Payment).where(Payment.order_id == order_id)
        )
        assert payment is not None
        payment.created_at = datetime.now(UTC) - timedelta(seconds=31)
        await context.session.commit()
        fake.create_error = None
        fake.query_error = WechatPayAPIError(
            "ORDER_NOT_EXIST",
            "order not exist",
            404,
        )

        recovered = await context.client.post(
            f"/api/v1/app/orders/{order_id}/payments/wechat",
            headers=auth,
        )
        assert recovered.status_code == 200, recovered.text
        assert recovered.json()["payment_id"] == str(payment.id)
        assert len(fake.created) == 2
        await context.session.refresh(payment)
        assert payment.status == PaymentStatus.PENDING
        assert payment.prepay_id == "wx-test-prepay-id"


async def test_late_success_closes_newer_pending_payment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings(
        _env_file=None,
        app_env="local",
        jwt_secret=JWT_SECRET,
        wechat_app_id=APP_ID,
        wechat_pay_mch_id=MCH_ID,
    )
    fake = FakeWechatPayProvider()
    monkeypatch.setattr(api_dependencies, "get_settings", lambda: settings)
    monkeypatch.setattr(orders_api, "get_settings", lambda: settings)

    async with api_context() as context:
        app.dependency_overrides[get_wechat_pay_provider] = lambda: fake
        store = make_store(f"迟到支付门店-{uuid4().hex[:8]}")
        context.session.add(store)
        await context.session.flush()
        product = make_product(store, name="迟到支付课程")
        sku = ProductSku(
            product=product,
            name="双课时",
            price_cents=8800,
            lesson_count=2,
            validity_days=60,
        )
        user = User(nickname="迟到支付学员")
        user.provider_accounts.append(
            ProviderAccount(
                provider=IdentityProvider.WEAPP,
                provider_subject="wechat-openid-late-payment",
            )
        )
        context.session.add_all((product, sku, user))
        await context.session.flush()
        token = create_access_token(
            user.id,
            JWT_SECRET,
            60,
            subject_type="user",
        )
        auth = {"Authorization": f"Bearer {token}"}
        order_response = await context.client.post(
            "/api/v1/app/orders",
            headers={**auth, "Idempotency-Key": "late-payment-order-key"},
            json={
                "store_id": str(store.id),
                "items": [
                    {
                        "product_id": str(product.id),
                        "sku_id": str(sku.id),
                        "quantity": 1,
                    }
                ],
            },
        )
        assert order_response.status_code == 201, order_response.text
        order_id = order_response.json()["id"]
        order = await context.session.get(Order, order_id)
        assert order is not None
        first_payment = Payment(
            order=order,
            attempt_no=1,
            merchant_order_no=f"{order.order_no}01",
            amount_cents=8800,
            status=PaymentStatus.CLOSED,
            expires_at=datetime.now(UTC) + timedelta(minutes=30),
        )
        second_payment = Payment(
            order=order,
            attempt_no=2,
            merchant_order_no=f"{order.order_no}02",
            amount_cents=8800,
            prepay_id="newer-prepay-id",
            expires_at=datetime.now(UTC) + timedelta(minutes=30),
        )
        context.session.add_all((first_payment, second_payment))
        await context.session.commit()
        fake.remote_order = WechatPayOrder(
            out_trade_no=first_payment.merchant_order_no,
            transaction_id="4200000000000000000000000099",
            trade_state="SUCCESS",
            amount_cents=8800,
            app_id=APP_ID,
            mch_id=MCH_ID,
            success_time=datetime.now(UTC),
        )

        webhook = await context.client.post(
            "/api/v1/webhooks/wechat-pay",
            headers={"Wechatpay-Serial": "TEST_PUBLIC_KEY_ID"},
            content=b"{}",
        )
        assert webhook.status_code == 200, webhook.text
        await context.session.refresh(first_payment)
        await context.session.refresh(second_payment)
        await context.session.refresh(order)
        assert first_payment.status == PaymentStatus.SUCCEEDED
        assert second_payment.status == PaymentStatus.CLOSED
        assert order.status == OrderStatus.CONFIRMED
        assert fake.closed == [second_payment.merchant_order_no]
