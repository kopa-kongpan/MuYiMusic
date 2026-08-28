import json
import re
import string
import unicodedata
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo

import httpx
from redis.asyncio import Redis

from app.core.config import Settings


class WechatSubscribeNotConfiguredError(Exception):
    pass


class WechatSubscribeDeliveryError(Exception):
    non_retryable_codes = {40003, 40037, 41030, 43101}
    token_error_codes = {40001, 40014, 42001}

    def __init__(self, code: int, message: str) -> None:
        self.code = code
        self.retryable = code not in self.non_retryable_codes
        super().__init__(f"wechat subscribe error {code}: {message}")


@dataclass(frozen=True)
class WechatSubscribeMessage:
    openid: str
    template_id: str
    page: str | None
    data: dict[str, dict[str, str]]


class WechatSubscribeProvider:
    token_cache_key = "muyimusic:wechat:access_token"
    local_timezone = ZoneInfo("Asia/Shanghai")

    def __init__(self, settings: Settings, redis: Redis) -> None:
        self.settings = settings
        self.redis = redis

    async def access_token(self) -> str:
        if not self.settings.wechat_app_id or not self.settings.wechat_app_secret:
            raise WechatSubscribeNotConfiguredError
        cached = await self.redis.get(self.token_cache_key)
        if cached:
            return cached.decode() if isinstance(cached, bytes) else str(cached)
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                "https://api.weixin.qq.com/cgi-bin/stable_token",
                json={
                    "grant_type": "client_credential",
                    "appid": self.settings.wechat_app_id,
                    "secret": self.settings.wechat_app_secret,
                    "force_refresh": False,
                },
            )
        response.raise_for_status()
        payload: dict[str, Any] = response.json()
        token = payload.get("access_token")
        if not isinstance(token, str):
            raise WechatSubscribeDeliveryError(
                int(payload.get("errcode", -1)),
                str(payload.get("errmsg", "token unavailable")),
            )
        expires_in = int(payload.get("expires_in", 7200))
        await self.redis.set(self.token_cache_key, token, ex=max(60, expires_in - 300))
        return token

    def template_id(self, template_key: str) -> str | None:
        return {
            "teacher_new_appointment": (
                self.settings.wechat_template_teacher_new_appointment
            ),
            "teacher_appointment_cancelled": (
                self.settings.wechat_template_teacher_appointment_cancelled
            ),
            "student_appointment_cancelled": (
                self.settings.wechat_template_student_appointment_cancelled
            ),
            "appointment_next_day_reminder": (
                self.settings.wechat_template_appointment_next_day_reminder
            ),
        }.get(template_key)

    def template_data(
        self, template_key: str, payload: dict[str, object]
    ) -> dict[str, dict[str, str]]:
        try:
            mappings = json.loads(self.settings.wechat_template_field_map_json)
        except json.JSONDecodeError as error:
            raise WechatSubscribeNotConfiguredError from error
        mapping = mappings.get(template_key, {}) if isinstance(mappings, dict) else {}
        if not isinstance(mapping, dict) or not mapping:
            raise WechatSubscribeNotConfiguredError
        result: dict[str, dict[str, str]] = {}
        for semantic_key, wechat_key in mapping.items():
            value = payload.get(semantic_key)
            if not isinstance(semantic_key, str) or not isinstance(wechat_key, str):
                raise WechatSubscribeNotConfiguredError
            if value is None:
                raise WechatSubscribeNotConfiguredError
            formatted = self._format_template_value(
                semantic_key=semantic_key,
                wechat_key=wechat_key,
                value=value,
            )
            if not formatted:
                raise WechatSubscribeNotConfiguredError
            result[wechat_key] = {"value": formatted}
        if not result:
            raise WechatSubscribeNotConfiguredError
        return result

    def _format_template_value(
        self,
        *,
        semantic_key: str,
        wechat_key: str,
        value: object,
    ) -> str:
        field_type = self._field_type(wechat_key)
        if semantic_key == "starts_at":
            local = self._local_datetime(value)
            if field_type == "time":
                return (
                    f"{local.year}年{local.month}月{local.day}日 "
                    f"{local.hour:02d}:{local.minute:02d}"
                )
            if field_type == "character_string":
                return local.strftime("%Y-%m-%d %H:%M")

        text = self._plain_text(value)
        if field_type == "thing":
            return text[:20]
        if field_type == "name":
            return self._name(text)
        if field_type == "character_string":
            allowed = string.ascii_letters + string.digits + string.punctuation + " "
            return "".join(character for character in text if character in allowed)[:32]
        return text

    @staticmethod
    def _field_type(wechat_key: str) -> str:
        match = re.fullmatch(r"([a-z_]+)\d+", wechat_key)
        if match is None:
            raise WechatSubscribeNotConfiguredError
        return match.group(1)

    @classmethod
    def _local_datetime(cls, value: object) -> datetime:
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError as error:
            raise WechatSubscribeNotConfiguredError from error
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed.astimezone(cls.local_timezone)

    @staticmethod
    def _plain_text(value: object) -> str:
        return " ".join(str(value).split())

    @staticmethod
    def _name(value: str) -> str:
        cleaned = "".join(
            character
            for character in value
            if not character.isdigit()
            and not unicodedata.category(character).startswith("C")
        ).strip()
        if not cleaned:
            return "微信用户"
        contains_cjk = any("\u4e00" <= character <= "\u9fff" for character in cleaned)
        return cleaned[: 10 if contains_cjk else 20]

    async def send(
        self,
        message: WechatSubscribeMessage,
        *,
        access_token: str | None = None,
    ) -> None:
        if not self.settings.wechat_app_id or not self.settings.wechat_app_secret:
            raise WechatSubscribeNotConfiguredError
        token = access_token or await self.access_token()
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                "https://api.weixin.qq.com/cgi-bin/message/subscribe/send",
                params={"access_token": token},
                json={
                    "touser": message.openid,
                    "template_id": message.template_id,
                    "page": message.page,
                    "data": message.data,
                    "miniprogram_state": (
                        "formal"
                        if self.settings.app_env == "production"
                        else "developer"
                    ),
                    "lang": "zh_CN",
                },
            )
        response.raise_for_status()
        payload = response.json()
        code = int(payload.get("errcode", -1))
        if code != 0:
            if code in WechatSubscribeDeliveryError.token_error_codes:
                await self.redis.delete(self.token_cache_key)
            raise WechatSubscribeDeliveryError(
                code, str(payload.get("errmsg", "unknown error"))
            )
