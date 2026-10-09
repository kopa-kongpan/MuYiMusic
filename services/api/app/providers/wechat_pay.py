import base64
import json
import secrets
import time
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

import httpx
from cryptography import x509
from cryptography.exceptions import InvalidSignature, InvalidTag
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import Settings, get_settings

WECHAT_PAY_API_ORIGIN = "https://api.mch.weixin.qq.com"


class WechatPayNotConfiguredError(Exception):
    pass


class WechatPayUnavailableError(Exception):
    pass


class WechatPaySignatureError(Exception):
    pass


class WechatPayAPIError(Exception):
    def __init__(self, code: str, message: str, status_code: int) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


@dataclass(frozen=True)
class WechatPayOrder:
    out_trade_no: str
    transaction_id: str | None
    trade_state: str
    amount_cents: int
    app_id: str
    mch_id: str
    success_time: datetime | None


@dataclass(frozen=True)
class WechatPayNotification:
    notification_id: str
    event_type: str
    order: WechatPayOrder


class WechatPayProvider:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def create_jsapi_payment(
        self,
        *,
        out_trade_no: str,
        description: str,
        amount_cents: int,
        openid: str,
        expires_at: datetime,
    ) -> str:
        app_id, mch_id, notify_url = self._merchant_config()
        payload = {
            "appid": app_id,
            "mchid": mch_id,
            "description": description[:127],
            "out_trade_no": out_trade_no,
            "time_expire": self._rfc3339(expires_at),
            "notify_url": notify_url,
            "amount": {"total": amount_cents, "currency": "CNY"},
            "payer": {"openid": openid},
        }
        response = await self._request(
            "POST",
            "/v3/pay/transactions/jsapi",
            payload,
        )
        prepay_id = response.get("prepay_id")
        if not isinstance(prepay_id, str) or not prepay_id:
            raise WechatPayUnavailableError("微信支付未返回 prepay_id")
        return prepay_id

    async def query_payment(self, out_trade_no: str) -> WechatPayOrder:
        _, mch_id, _ = self._merchant_config()
        payload = await self._request(
            "GET",
            f"/v3/pay/transactions/out-trade-no/{out_trade_no}?mchid={mch_id}",
        )
        return self._parse_order(payload)

    async def close_payment(self, out_trade_no: str) -> None:
        _, mch_id, _ = self._merchant_config()
        await self._request(
            "POST",
            f"/v3/pay/transactions/out-trade-no/{out_trade_no}/close",
            {"mchid": mch_id},
            expect_empty=True,
        )

    def client_parameters(self, prepay_id: str) -> dict[str, str]:
        app_id, _, _ = self._merchant_config()
        timestamp = str(int(time.time()))
        nonce = secrets.token_urlsafe(24)[:32]
        package = f"prepay_id={prepay_id}"
        message = f"{app_id}\n{timestamp}\n{nonce}\n{package}\n"
        return {
            "timeStamp": timestamp,
            "nonceStr": nonce,
            "package": package,
            "signType": "RSA",
            "paySign": self._sign(message),
        }

    def parse_notification(
        self,
        headers: httpx.Headers,
        body: bytes,
    ) -> WechatPayNotification:
        self._verify_signature(headers, body)
        try:
            envelope = json.loads(body)
            resource = envelope["resource"]
            if resource.get("algorithm") != "AEAD_AES_256_GCM":
                raise ValueError("unsupported notification algorithm")
            ciphertext = base64.b64decode(resource["ciphertext"])
            nonce = resource["nonce"].encode()
            associated_data = resource.get("associated_data", "").encode()
            plaintext = AESGCM(self._api_v3_key()).decrypt(
                nonce,
                ciphertext,
                associated_data,
            )
            payload = json.loads(plaintext)
        except (InvalidTag, KeyError, TypeError, ValueError) as error:
            raise WechatPaySignatureError("微信支付通知格式或密文无效") from error
        notification_id = envelope.get("id")
        event_type = envelope.get("event_type")
        if not isinstance(notification_id, str) or not isinstance(event_type, str):
            raise WechatPaySignatureError("微信支付通知缺少事件标识")
        return WechatPayNotification(
            notification_id=notification_id,
            event_type=event_type,
            order=self._parse_order(payload),
        )

    async def _request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        *,
        expect_empty: bool = False,
    ) -> dict[str, Any]:
        body = (
            json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
            if payload is not None
            else ""
        )
        timestamp = str(int(time.time()))
        nonce = secrets.token_urlsafe(24)[:32]
        message = f"{method}\n{path}\n{timestamp}\n{nonce}\n{body}\n"
        mch_id = self.settings.wechat_pay_mch_id
        serial_no = self.settings.wechat_pay_merchant_serial_no
        if not mch_id or not serial_no:
            raise WechatPayNotConfiguredError
        authorization = (
            'WECHATPAY2-SHA256-RSA2048 '
            f'mchid="{mch_id}",nonce_str="{nonce}",'
            f'signature="{self._sign(message)}",timestamp="{timestamp}",'
            f'serial_no="{serial_no}"'
        )
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.request(
                    method,
                    f"{WECHAT_PAY_API_ORIGIN}{path}",
                    content=body.encode() if body else None,
                    headers={
                        "Accept": "application/json",
                        "Content-Type": "application/json",
                        "Authorization": authorization,
                        "User-Agent": "MuYiMusic/1.0",
                    },
                )
        except httpx.HTTPError as error:
            raise WechatPayUnavailableError("微信支付服务暂时不可用") from error
        self._verify_signature(response.headers, response.content)
        if response.status_code >= 400:
            try:
                error_payload = response.json()
            except ValueError:
                error_payload = {}
            code = error_payload.get("code", "WECHAT_PAY_ERROR")
            message = error_payload.get("message", "微信支付请求失败")
            raise WechatPayAPIError(str(code), str(message), response.status_code)
        if expect_empty or response.status_code == 204 or not response.content:
            return {}
        try:
            result = response.json()
        except ValueError as error:
            raise WechatPayUnavailableError("微信支付响应格式无效") from error
        if not isinstance(result, dict):
            raise WechatPayUnavailableError("微信支付响应格式无效")
        return result

    def _merchant_config(self) -> tuple[str, str, str]:
        if not self.settings.has_wechat_pay_credentials():
            raise WechatPayNotConfiguredError
        assert self.settings.wechat_app_id is not None
        assert self.settings.wechat_pay_mch_id is not None
        assert self.settings.wechat_pay_notify_url is not None
        return (
            self.settings.wechat_app_id,
            self.settings.wechat_pay_mch_id,
            self.settings.wechat_pay_notify_url,
        )

    def _private_key(self) -> rsa.RSAPrivateKey:
        path = self.settings.wechat_pay_private_key_path
        if not path:
            raise WechatPayNotConfiguredError
        try:
            loaded = serialization.load_pem_private_key(
                Path(path).read_bytes(),
                password=None,
            )
        except (OSError, ValueError, TypeError) as error:
            raise WechatPayNotConfiguredError from error
        if not isinstance(loaded, rsa.RSAPrivateKey):
            raise WechatPayNotConfiguredError
        return loaded

    def _public_key(self) -> rsa.RSAPublicKey:
        path = self.settings.wechat_pay_public_key_path
        if not path:
            raise WechatPayNotConfiguredError
        try:
            pem = Path(path).read_bytes()
            try:
                loaded = serialization.load_pem_public_key(pem)
            except ValueError:
                loaded = x509.load_pem_x509_certificate(pem).public_key()
        except (OSError, ValueError, TypeError) as error:
            raise WechatPayNotConfiguredError from error
        if not isinstance(loaded, rsa.RSAPublicKey):
            raise WechatPayNotConfiguredError
        return loaded

    def _api_v3_key(self) -> bytes:
        value = self.settings.wechat_pay_api_v3_key
        if value is None or len(value.encode()) != 32:
            raise WechatPayNotConfiguredError
        return value.encode()

    def _sign(self, message: str) -> str:
        signature = self._private_key().sign(
            message.encode(),
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
        return base64.b64encode(signature).decode()

    def _verify_signature(self, headers: httpx.Headers, body: bytes) -> None:
        timestamp = headers.get("Wechatpay-Timestamp")
        nonce = headers.get("Wechatpay-Nonce")
        signature = headers.get("Wechatpay-Signature")
        serial = headers.get("Wechatpay-Serial")
        expected_serial = self.settings.wechat_pay_public_key_id
        if (
            not timestamp
            or not nonce
            or not signature
            or not serial
            or not expected_serial
            or serial != expected_serial
        ):
            raise WechatPaySignatureError("微信支付签名头无效")
        try:
            if abs(int(time.time()) - int(timestamp)) > 300:
                raise WechatPaySignatureError("微信支付签名时间戳已过期")
            decoded = base64.b64decode(signature, validate=True)
            message = f"{timestamp}\n{nonce}\n{body.decode()}\n"
            self._public_key().verify(
                decoded,
                message.encode(),
                padding.PKCS1v15(),
                hashes.SHA256(),
            )
        except (InvalidSignature, UnicodeDecodeError, ValueError) as error:
            raise WechatPaySignatureError("微信支付响应签名校验失败") from error

    @staticmethod
    def _rfc3339(value: datetime) -> str:
        return value.isoformat(timespec="seconds").replace("+00:00", "Z")

    @staticmethod
    def _parse_order(payload: dict[str, Any]) -> WechatPayOrder:
        try:
            amount = payload["amount"]
            success_time_raw = payload.get("success_time")
            success_time = (
                datetime.fromisoformat(success_time_raw.replace("Z", "+00:00"))
                if isinstance(success_time_raw, str)
                else None
            )
            return WechatPayOrder(
                out_trade_no=str(payload["out_trade_no"]),
                transaction_id=(
                    str(payload["transaction_id"])
                    if payload.get("transaction_id")
                    else None
                ),
                trade_state=str(payload["trade_state"]),
                amount_cents=int(amount["total"]),
                app_id=str(payload["appid"]),
                mch_id=str(payload["mchid"]),
                success_time=success_time,
            )
        except (KeyError, TypeError, ValueError) as error:
            raise WechatPayUnavailableError("微信支付订单数据无效") from error


@lru_cache
def get_wechat_pay_provider() -> WechatPayProvider:
    return WechatPayProvider(get_settings())
