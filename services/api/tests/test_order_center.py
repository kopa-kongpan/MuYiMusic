from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.models.payment import Payment, PaymentStatus
from app.models.user import Order, OrderItem, OrderStatus
from app.services.payment_service import PaymentService
from tests.conftest import api_context, create_user_login, make_store

pytestmark = pytest.mark.asyncio


async def test_order_center_resolves_payment_number_and_enforces_ownership() -> None:
    async with api_context() as context:
        owner, headers = await create_user_login(
            context.client, context.session, "订单中心学员"
        )
        _, other_headers = await create_user_login(
            context.client, context.session, "另一位学员"
        )
        store = make_store("订单所属门店")
        context.session.add(store)
        await context.session.flush()
        order = Order(
            order_no=f"O{uuid4().hex[:30]}",
            user_id=owner.id,
            store_id=store.id,
            status=OrderStatus.CONFIRMED,
            total_amount_cents=100,
        )
        order.items.append(
            OrderItem(
                product_name="钢琴进阶考级课",
                sku_name="10次卡",
                unit_price_cents=100,
                quantity=1,
                total_amount_cents=100,
                lesson_count=10,
                validity_days=180,
            )
        )
        paid_at = datetime.now(UTC)
        payment_number = f"P{uuid4().hex[:30]}"
        order.payments.append(
            Payment(
                merchant_order_no=payment_number,
                attempt_no=1,
                amount_cents=100,
                status=PaymentStatus.SUCCEEDED,
                paid_at=paid_at,
                expires_at=paid_at + timedelta(minutes=30),
            )
        )
        # 后创建但已关闭的支付尝试不能遮蔽真正成功的交易。
        order.payments.append(
            Payment(
                merchant_order_no=f"P{uuid4().hex[:30]}",
                attempt_no=2,
                amount_cents=100,
                status=PaymentStatus.CLOSED,
                expires_at=paid_at + timedelta(minutes=30),
            )
        )
        context.session.add(order)
        await context.session.flush()
        for number in (payment_number, order.order_no):
            url = f"/api/v1/app/me/orders/{number}"
            result = await context.client.get(url, headers=headers)
            assert result.status_code == 200, result.text
            payload = result.json()
            assert payload["id"] == str(order.id)
            assert payload["store_name"] == store.name
            assert payload["store_phone"] == store.phone
            assert payload["items"][0]["sku_name"] == "10次卡"
            assert payload["payment_status"] == "succeeded"
            assert payload["paid_at"] is not None
            assert "payer_openid" not in payload
            assert (
                await context.client.get(url, headers=other_headers)
            ).status_code == 404
            assert (await context.client.get(url)).status_code == 401

        order.payments[0].status = PaymentStatus.REFUNDED
        await context.session.flush()
        refunded = await context.client.get(
            f"/api/v1/app/me/orders/{payment_number}", headers=headers
        )
        assert refunded.json()["payment_status"] == "refunded"
        missing = await context.client.get(
            "/api/v1/app/me/orders/not-found", headers=headers
        )
        assert missing.status_code == 404


async def test_description_contains_product_sku_quantity_and_is_bounded() -> None:
    order = Order()
    order.items = [
        OrderItem(product_name="钢琴进阶考级课", sku_name="10次卡", quantity=2),
        OrderItem(product_name="声乐课", sku_name="单次体验", quantity=1),
    ]
    description = PaymentService._description(order)
    assert "钢琴进阶考级课 10次卡 ×2" in description
    assert "声乐课 单次体验 ×1" in description
    order.items[0].product_name = "钢琴课程" * 50
    assert len(PaymentService._description(order)) == 127
