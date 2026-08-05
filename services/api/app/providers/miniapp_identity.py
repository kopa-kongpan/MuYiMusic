import hashlib
from dataclasses import dataclass
from functools import lru_cache

import httpx

from app.core.config import Settings, get_settings
from app.models.user import IdentityProvider


class IdentityProviderNotConfiguredError(Exception):
    pass


class InvalidPlatformCodeError(Exception):
    pass


class IdentityProviderUnavailableError(Exception):
    pass


@dataclass(frozen=True)
class ProviderIdentity:
    subject: str
    union_subject: str | None = None


class MiniAppIdentityProvider:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def exchange(
        self,
        provider: IdentityProvider,
        code: str,
    ) -> ProviderIdentity:
        if provider == IdentityProvider.H5:
            return self._exchange_local(code)
        if provider == IdentityProvider.WEAPP:
            return await self._exchange_wechat(code)
        return await self._exchange_douyin(code)

    def _exchange_local(self, code: str) -> ProviderIdentity:
        if self.settings.app_env != "local":
            raise IdentityProviderNotConfiguredError
        if len(code) < 20:
            raise InvalidPlatformCodeError
        subject = hashlib.sha256(code.encode()).hexdigest()
        return ProviderIdentity(subject=f"local_{subject}")

    async def _exchange_wechat(self, code: str) -> ProviderIdentity:
        if not self.settings.wechat_app_id or not self.settings.wechat_app_secret:
            raise IdentityProviderNotConfiguredError
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                response = await client.get(
                    "https://api.weixin.qq.com/sns/jscode2session",
                    params={
                        "appid": self.settings.wechat_app_id,
                        "secret": self.settings.wechat_app_secret,
                        "js_code": code,
                        "grant_type": "authorization_code",
                    },
                )
        except httpx.HTTPError as error:
            raise IdentityProviderUnavailableError from error
        if response.status_code != 200:
            raise InvalidPlatformCodeError
        try:
            payload = response.json()
        except ValueError as error:
            raise IdentityProviderUnavailableError from error
        subject = payload.get("openid")
        if not isinstance(subject, str) or not subject:
            raise InvalidPlatformCodeError
        union_subject = payload.get("unionid")
        return ProviderIdentity(
            subject=subject,
            union_subject=union_subject if isinstance(union_subject, str) else None,
        )

    async def _exchange_douyin(self, code: str) -> ProviderIdentity:
        if not self.settings.douyin_app_id or not self.settings.douyin_app_secret:
            raise IdentityProviderNotConfiguredError
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                response = await client.post(
                    "https://developer.toutiao.com/api/apps/v2/jscode2session",
                    json={
                        "appid": self.settings.douyin_app_id,
                        "secret": self.settings.douyin_app_secret,
                        "code": code,
                    },
                )
        except httpx.HTTPError as error:
            raise IdentityProviderUnavailableError from error
        if response.status_code != 200:
            raise InvalidPlatformCodeError
        try:
            payload = response.json()
        except ValueError as error:
            raise IdentityProviderUnavailableError from error
        data = payload.get("data")
        if not isinstance(data, dict):
            raise InvalidPlatformCodeError
        subject = data.get("openid")
        if not isinstance(subject, str) or not subject:
            raise InvalidPlatformCodeError
        union_subject = data.get("unionid")
        return ProviderIdentity(
            subject=subject,
            union_subject=union_subject if isinstance(union_subject, str) else None,
        )


@lru_cache
def get_miniapp_identity_provider() -> MiniAppIdentityProvider:
    return MiniAppIdentityProvider(get_settings())
