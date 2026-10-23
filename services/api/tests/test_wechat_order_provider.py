import json
import logging
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest

from app.core.config import Settings
from app.providers.wechat_order import (
    WechatOrderAPIError,
    WechatOrderProvider,
    WechatOrderUnavailableError,
)

pytestmark = pytest.mark.asyncio


class FakeRedis:
    def __init__(self) -> None:
        self.deleted: list[str] = []

    async def delete(self, key: str) -> None:
        self.deleted.append(key)


class FakeTokens:
    token_cache_key = "test-token-cache"

    def __init__(self) -> None:
        self.calls = 0

    async def access_token(self) -> str:
        self.calls += 1
        return f"secret-token-{self.calls}"


def provider(handler: Any) -> tuple[WechatOrderProvider, FakeRedis]:
    redis = FakeRedis()
    instance = WechatOrderProvider(
        Settings(_env_file=None), redis, transport=httpx.MockTransport(handler)
    )
    instance.token_provider = FakeTokens()
    return instance, redis


async def test_shipping_payload_and_expired_token_refresh(
    caplog: pytest.LogCaptureFixture,
) -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if len(requests) == 1:
            return httpx.Response(200, json={"errcode": 42001, "errmsg": "expired"})
        return httpx.Response(200, json={"errcode": 0})

    instance, redis = provider(handler)
    confirmed_at = datetime.now(UTC)
    with caplog.at_level(logging.INFO):
        await instance.upload_shipping(
            transaction_id="test-transaction",
            openid="test-openid",
            logistics_type=3,
            item_description="钢琴课服务交付",
            confirmed_at=confirmed_at,
        )
    assert redis.deleted == ["test-token-cache"]
    assert len(requests) == 2
    assert requests[0].url.params["access_token"] == "secret-token-1"
    assert requests[1].url.params["access_token"] == "secret-token-2"
    payload = json.loads(requests[-1].content)
    assert payload == {
        "order_key": {"order_number_type": 2, "transaction_id": "test-transaction"},
        "logistics_type": 3,
        "delivery_mode": 1,
        "shipping_list": [{"item_desc": "钢琴课服务交付"}],
        "upload_time": confirmed_at.isoformat(timespec="milliseconds"),
        "payer": {"openid": "test-openid"},
    }
    assert "secret-token" not in caplog.text
    assert "test-openid" not in caplog.text


async def test_wechat_error_never_copies_sensitive_raw_message() -> None:
    instance, _ = provider(
        lambda request: httpx.Response(
            200,
            json={
                "errcode": 48001,
                "errmsg": "secret-token=test&openid=private-user",
            },
        )
    )
    with pytest.raises(WechatOrderAPIError) as error:
        await instance.get_order("test-transaction")
    assert error.value.code == 48001
    assert "secret-token" not in str(error.value)
    assert "private-user" not in str(error.value)


@pytest.mark.parametrize("delivered", [True, False, "false"])
async def test_shipping_query_requires_valid_delivery_state(delivered: Any) -> None:
    instance, _ = provider(
        lambda request: httpx.Response(
            200,
            json={
                "errcode": 0,
                "order": {
                    "transaction_id": "test-transaction",
                    "merchant_id": "merchant",
                    "merchant_trade_no": "order",
                    "paid_amount": 9800,
                    "openid": "user",
                    "order_state": 2,
                    "shipping": {"finish_shipping": delivered},
                },
            },
        )
    )
    if isinstance(delivered, bool):
        assert (await instance.get_order("test-transaction")).delivered is delivered
    else:
        with pytest.raises(WechatOrderUnavailableError):
            await instance.get_order("test-transaction")
