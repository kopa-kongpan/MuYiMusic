from typing import Annotated
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.core.config import get_settings
from app.core.database import get_session
from app.models.user import User
from app.providers.wechat_pay import (
    WechatPayAPIError,
    WechatPayNotConfiguredError,
    WechatPayProvider,
    WechatPaySignatureError,
    WechatPayUnavailableError,
    get_wechat_pay_provider,
)
from app.schemas.order import (
    OrderCreate,
    OrderPaymentStatusResponse,
    WechatPaymentParameters,
)
from app.schemas.user import OrderRead
from app.services.payment_service import (
    InvalidOrderError,
    PaymentConflictError,
    PaymentResourceNotFoundError,
    PaymentService,
    WechatIdentityRequiredError,
)

router = APIRouter(tags=["app-orders"])
webhook_router = APIRouter(prefix="/webhooks", tags=["payment-webhooks"])
ProviderDependency = Annotated[
    WechatPayProvider,
    Depends(get_wechat_pay_provider),
]


def payment_service(
    session: AsyncSession,
    provider: WechatPayProvider,
) -> PaymentService:
    return PaymentService(session, get_settings(), provider)


@router.post(
    "/orders",
    response_model=OrderRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_order(
    payload: OrderCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_user)],
    provider: ProviderDependency,
    idempotency_key: Annotated[
        str,
        Header(alias="Idempotency-Key", min_length=8, max_length=128),
    ],
) -> OrderRead:
    try:
        return await payment_service(session, provider).create_order(
            user=current_user,
            payload=payload,
            idempotency_key=idempotency_key,
        )
    except InvalidOrderError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.post(
    "/orders/{order_id}/payments/wechat",
    response_model=WechatPaymentParameters,
)
async def create_wechat_payment(
    order_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_user)],
    provider: ProviderDependency,
) -> WechatPaymentParameters:
    try:
        return await payment_service(session, provider).create_wechat_payment(
            user=current_user,
            order_id=order_id,
        )
    except PaymentResourceNotFoundError as error:
        raise HTTPException(status_code=404, detail="订单不存在") from error
    except WechatIdentityRequiredError as error:
        raise HTTPException(
            status_code=409,
            detail="当前账号未绑定微信小程序身份，请在微信小程序中重新登录",
        ) from error
    except PaymentConflictError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except WechatPayNotConfiguredError as error:
        raise HTTPException(status_code=503, detail="微信支付尚未配置") from error
    except (WechatPayUnavailableError, WechatPaySignatureError) as error:
        raise HTTPException(status_code=502, detail="微信支付服务暂时不可用") from error
    except WechatPayAPIError as error:
        raise HTTPException(
            status_code=502,
            detail=f"微信支付下单失败：{error.message}",
        ) from error


@router.post(
    "/orders/{order_id}/payments/wechat/query",
    response_model=OrderPaymentStatusResponse,
)
async def query_wechat_payment(
    order_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_user)],
    provider: ProviderDependency,
) -> OrderPaymentStatusResponse:
    try:
        return await payment_service(session, provider).query_order_payment(
            user=current_user,
            order_id=order_id,
        )
    except PaymentResourceNotFoundError as error:
        raise HTTPException(status_code=404, detail="订单不存在") from error
    except PaymentConflictError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except WechatPayNotConfiguredError as error:
        raise HTTPException(status_code=503, detail="微信支付尚未配置") from error
    except (WechatPayUnavailableError, WechatPaySignatureError) as error:
        raise HTTPException(status_code=502, detail="微信支付查单失败") from error
    except WechatPayAPIError as error:
        raise HTTPException(
            status_code=502,
            detail=f"微信支付查单失败：{error.message}",
        ) from error


@webhook_router.post("/wechat-pay")
async def wechat_pay_webhook(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    provider: ProviderDependency,
) -> dict[str, str]:
    body = await request.body()
    try:
        notification = provider.parse_notification(httpx.Headers(request.headers), body)
        await payment_service(session, provider).handle_notification(notification)
    except WechatPaySignatureError as error:
        raise HTTPException(status_code=401, detail="微信支付通知验签失败") from error
    except PaymentResourceNotFoundError as error:
        raise HTTPException(status_code=404, detail="支付单不存在") from error
    except PaymentConflictError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except WechatPayNotConfiguredError as error:
        raise HTTPException(status_code=503, detail="微信支付尚未配置") from error
    return {"code": "SUCCESS", "message": "成功"}
