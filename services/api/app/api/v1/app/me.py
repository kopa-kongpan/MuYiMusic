from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.core.config import get_settings
from app.core.database import get_session
from app.models.user import EntitlementStatus, OrderStatus, User
from app.providers.miniapp_identity import get_miniapp_identity_provider
from app.providers.object_storage import get_object_storage
from app.schemas.user import (
    CourseEntitlementListResponse,
    OrderListResponse,
    UserProfile,
    UserProfileUpdate,
)
from app.services.user_service import UserService, user_profile

router = APIRouter(prefix="/me", tags=["app-me"])
CurrentUser = Annotated[User, Depends(get_current_user)]


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
