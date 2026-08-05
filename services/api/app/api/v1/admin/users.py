from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import require_permission
from app.core.config import get_settings
from app.core.database import get_session
from app.models.admin import AdminUser
from app.models.user import EntitlementStatus, OrderStatus
from app.providers.miniapp_identity import get_miniapp_identity_provider
from app.schemas.user import (
    CourseEntitlementListResponse,
    OrderListResponse,
    UserAdminListResponse,
)
from app.services.user_service import UserResourceNotFoundError, UserService

router = APIRouter(prefix="/stores/{store_id}/users", tags=["admin-users"])
UserReader = Annotated[AdminUser, Depends(require_permission("users:read"))]


def service(session: AsyncSession) -> UserService:
    return UserService(
        session,
        get_settings(),
        get_miniapp_identity_provider(),
    )


@router.get("", response_model=UserAdminListResponse)
async def list_users(
    store_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    current_admin: UserReader,
    keyword: Annotated[str | None, Query(max_length=128)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> UserAdminListResponse:
    try:
        return await service(session).list_users_admin(
            store_id=store_id,
            admin_user=current_admin,
            keyword=keyword,
            page=page,
            page_size=page_size,
        )
    except UserResourceNotFoundError as error:
        raise HTTPException(status_code=404, detail="门店不存在") from error


@router.get("/{user_id}/orders", response_model=OrderListResponse)
async def list_user_orders(
    store_id: UUID,
    user_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    current_admin: UserReader,
    order_status: Annotated[OrderStatus | None, Query(alias="status")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> OrderListResponse:
    try:
        return await service(session).list_user_orders_admin(
            store_id=store_id,
            user_id=user_id,
            admin_user=current_admin,
            status=order_status,
            page=page,
            page_size=page_size,
        )
    except UserResourceNotFoundError as error:
        raise HTTPException(status_code=404, detail="门店不存在") from error


@router.get(
    "/{user_id}/course-entitlements",
    response_model=CourseEntitlementListResponse,
)
async def list_user_entitlements(
    store_id: UUID,
    user_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    current_admin: UserReader,
    entitlement_status: Annotated[
        EntitlementStatus | None,
        Query(alias="status"),
    ] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> CourseEntitlementListResponse:
    try:
        return await service(session).list_user_entitlements_admin(
            store_id=store_id,
            user_id=user_id,
            admin_user=current_admin,
            status=entitlement_status,
            page=page,
            page_size=page_size,
        )
    except UserResourceNotFoundError as error:
        raise HTTPException(status_code=404, detail="门店不存在") from error
