from dataclasses import dataclass
from datetime import datetime
from typing import Any

import httpx
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.config import Settings
from app.providers.wechat_subscribe import (
    WechatSubscribeDeliveryError,
    WechatSubscribeNotConfiguredError,
    WechatSubscribeProvider,
)


class WechatOrderUnavailableError(Exception):
    pass


class WechatOrderAPIError(Exception):
    def __init__(self, code: int) -> None:
        self.code = code
        # 不保存微信原始 errmsg，避免把 openid、access_token 等带入日志。
        super().__init__(f"微信订单管理请求失败（错误码 {code}）")


@dataclass(frozen=True)
class WechatShippingOrder:
    transaction_id: str
    merchant_id: str
    merchant_trade_no: str
    amount_cents: int
    openid: str
    order_state: int
    delivered: bool


class WechatOrderProvider:
    token_error_codes = {40001, 40014, 42001}

    def __init__(
        self,
        settings: Settings,
        redis: Redis,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.token_provider = WechatSubscribeProvider(settings, redis)
        self.redis = redis
        self.transport = transport

    async def get_order(self, transaction_id: str) -> WechatShippingOrder:
        payload = await self._request("get_order", {"transaction_id": transaction_id})
        try:
            order = payload["order"]
            shipping = order.get("shipping") or {}
            delivered = shipping.get("finish_shipping", False)
            if not isinstance(delivered, bool):
                raise ValueError("invalid shipping state")
            result = WechatShippingOrder(
                transaction_id=order["transaction_id"],
                merchant_id=order["merchant_id"],
                merchant_trade_no=order["merchant_trade_no"],
                amount_cents=int(order["paid_amount"]),
                openid=order["openid"],
                order_state=int(order["order_state"]),
                delivered=delivered,
            )
            if not all(
                isinstance(value, str) and value
                for value in (
                    result.transaction_id,
                    result.merchant_id,
                    result.merchant_trade_no,
                    result.openid,
                )
            ):
                raise ValueError("invalid shipping order")
            return result
        except (KeyError, TypeError, ValueError, AttributeError) as error:
            raise WechatOrderUnavailableError("微信订单管理响应格式无效") from error

    async def upload_shipping(
        self,
        *,
        transaction_id: str,
        openid: str,
        logistics_type: int,
        item_description: str,
        confirmed_at: datetime,
    ) -> None:
        await self._request(
            "upload_shipping_info",
            {
                "order_key": {"order_number_type": 2, "transaction_id": transaction_id},
                "logistics_type": logistics_type,
                "delivery_mode": 1,
                "shipping_list": [{"item_desc": item_description}],
                "upload_time": confirmed_at.isoformat(timespec="milliseconds"),
                "payer": {"openid": openid},
            },
        )

    async def _request(
        self, operation: str, payload: dict[str, object]
    ) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(
                timeout=10, transport=self.transport
            ) as client:
                for attempt in range(2):
                    token = await self.token_provider.access_token()
                    response = await client.post(
                        f"https://api.weixin.qq.com/wxa/sec/order/{operation}",
                        params={"access_token": token},
                        json=payload,
                    )
                    response.raise_for_status()
                    result: Any = response.json()
                    if not isinstance(result, dict) or "errcode" not in result:
                        raise ValueError("invalid response")
                    code = int(result["errcode"])
                    if code in self.token_error_codes and attempt == 0:
                        await self.redis.delete(self.token_provider.token_cache_key)
                        continue
                    if code != 0:
                        raise WechatOrderAPIError(code)
                    return result
        except WechatSubscribeNotConfiguredError as error:
            raise WechatOrderUnavailableError("微信订单管理尚未配置") from error
        except WechatSubscribeDeliveryError as error:
            raise WechatOrderAPIError(error.code) from error
        except (httpx.HTTPError, RedisError, ValueError) as error:
            raise WechatOrderUnavailableError("微信订单管理服务暂时不可用") from error
        raise WechatOrderUnavailableError("微信订单管理凭据刷新失败")
