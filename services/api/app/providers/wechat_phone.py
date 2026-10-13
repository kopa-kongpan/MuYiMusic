from dataclasses import dataclass
from typing import Any

import httpx
from redis.asyncio import Redis

from app.core.config import Settings
from app.providers.wechat_subscribe import (
    WechatSubscribeDeliveryError,
    WechatSubscribeNotConfiguredError,
    WechatSubscribeProvider,
)


class WechatPhoneNotConfiguredError(Exception):
    pass


class InvalidWechatPhoneCodeError(Exception):
    pass


class WechatPhoneUnavailableError(Exception):
    pass


@dataclass(frozen=True)
class WechatPhoneNumber:
    phone_number: str
    country_code: str


class WechatPhoneProvider:
    endpoint = "https://api.weixin.qq.com/wxa/business/getuserphonenumber"
    token_error_codes = {40001, 40014, 42001}
    invalid_code_error_codes = {40029, 40163}

    def __init__(self, settings: Settings, redis: Redis) -> None:
        self.redis = redis
        self.token_provider = WechatSubscribeProvider(settings, redis)

    async def exchange(self, code: str) -> WechatPhoneNumber:
        try:
            token = await self.token_provider.access_token()
            payload = await self._request(token, code)
            if self._error_code(payload) in self.token_error_codes:
                await self.redis.delete(self.token_provider.token_cache_key)
                token = await self.token_provider.access_token()
                payload = await self._request(token, code)
        except WechatSubscribeNotConfiguredError as error:
            raise WechatPhoneNotConfiguredError from error
        except (WechatSubscribeDeliveryError, httpx.HTTPError, ValueError) as error:
            raise WechatPhoneUnavailableError from error

        error_code = self._error_code(payload)
        if error_code in self.invalid_code_error_codes:
            raise InvalidWechatPhoneCodeError
        if error_code != 0:
            raise WechatPhoneUnavailableError
        phone_info = payload.get("phone_info")
        if not isinstance(phone_info, dict):
            raise WechatPhoneUnavailableError
        phone_number = phone_info.get("purePhoneNumber") or phone_info.get(
            "phoneNumber"
        )
        country_code = phone_info.get("countryCode")
        if not isinstance(phone_number, str) or not phone_number.isdigit():
            raise WechatPhoneUnavailableError
        if not isinstance(country_code, str):
            country_code = ""
        return WechatPhoneNumber(
            phone_number=phone_number,
            country_code=country_code,
        )

    @staticmethod
    def _error_code(payload: dict[str, Any]) -> int:
        try:
            return int(payload.get("errcode", -1))
        except (TypeError, ValueError):
            return -1

    async def _request(self, token: str, code: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                self.endpoint,
                params={"access_token": token},
                json={"code": code},
            )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise WechatPhoneUnavailableError
        return payload
