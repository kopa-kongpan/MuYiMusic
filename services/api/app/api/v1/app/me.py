from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.core.config import get_settings
from app.core.database import get_session
from app.core.redis import get_redis
from app.models.user import EntitlementStatus, OrderStatus, User
from app.providers.miniapp_identity import get_miniapp_identity_provider
from app.providers.object_storage import get_object_storage
from app.providers.wechat_phone import (
    InvalidWechatPhoneCodeError,
    WechatPhoneNotConfiguredError,
    WechatPhoneProvider,
    WechatPhoneUnavailableError,
)
from app.schemas.user import (
    CourseEntitlementListResponse,
    OrderListResponse,
    UserProfile,
    UserProfileUpdate,
    WechatPhoneBindRequest,
)
from app.services.user_service import PhoneAlreadyBoundError, UserService, user_profile

router = APIRouter(prefix="/me", tags=["app-me"])
CurrentUser = Annotated[User, Depends(get_current_user)]
RedisDependency = Annotated[Redis, Depends(get_redis)]


def get_wechat_phone_provider(redis: RedisDependency) -> WechatPhoneProvider:
    return WechatPhoneProvider(get_settings(), redis)


WechatPhoneProviderDependency = Annotated[
    WechatPhoneProvider,
    Depends(get_wechat_phone_provider),
]


@router.get("", response_model=UserProfile)
async def get_profile(current_user: CurrentUser) -> UserProfile:
    return user_profile(current_user)


@router.patch("", response_model=UserProfile)
async def update_profile(
    payload: UserProfileUpdate,
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> UserProfile:
    return await UserService(
        session,
        get_settings(),
        get_miniapp_identity_provider(),
    ).update_profile(current_user, payload)


@router.post("/phone", response_model=UserProfile)
async def bind_wechat_phone(
    payload: WechatPhoneBindRequest,
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_session)],
    provider: WechatPhoneProviderDependency,
) -> UserProfile:
    try:
        return await UserService(
            session,
            get_settings(),
            get_miniapp_identity_provider(),
        ).bind_wechat_phone(current_user, payload, provider)
    except WechatPhoneNotConfiguredError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="微信手机号能力尚未配置",
        ) from error
    except InvalidWechatPhoneCodeError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="手机号授权已失效，请重新授权",
        ) from error
    except WechatPhoneUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="微信手机号服务暂时不可用，请稍后重试",
        ) from error
    except PhoneAlreadyBoundError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="该手机号已绑定其他账号，请联系门店处理",
        ) from error


@router.get("/orders", response_model=OrderListResponse)
async def list_orders(
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_session)],
    store_id: UUID | None = None,
    order_status: Annotated[OrderStatus | None, Query(alias="status")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> OrderListResponse:
    return await UserService(
        session,
        get_settings(),
        get_miniapp_identity_provider(),
    ).list_orders(
        user_id=current_user.id,
        store_id=store_id,
        status=order_status,
        page=page,
        page_size=page_size,
    )


@router.get("/course-entitlements", response_model=CourseEntitlementListResponse)
async def list_entitlements(
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_session)],
    store_id: UUID | None = None,
    entitlement_status: Annotated[
        EntitlementStatus | None,
        Query(alias="status"),
    ] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> CourseEntitlementListResponse:
    return await UserService(
        session,
        get_settings(),
        get_miniapp_identity_provider(),
        storage=get_object_storage(),
    ).list_entitlements(
        user_id=current_user.id,
        store_id=store_id,
        status=entitlement_status,
        page=page,
        page_size=page_size,
    )
