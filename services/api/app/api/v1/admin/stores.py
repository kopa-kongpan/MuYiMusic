from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_admin, require_permission
from app.core.database import get_session
from app.models.admin import AdminUser
from app.models.store import StoreStatus
from app.schemas.store import (
    StoreAdminListResponse,
    StoreCreate,
    StoreRead,
    StoreUpdate,
)
from app.services.store_service import StoreNotFoundError, StoreService

router = APIRouter(prefix="/stores", tags=["admin-stores"])
StoreManager = Annotated[
    AdminUser,
    Depends(require_permission("stores:manage")),
]


@router.get("", response_model=StoreAdminListResponse)
async def list_stores(
    session: Annotated[AsyncSession, Depends(get_session)],
    current_admin: Annotated[AdminUser, Depends(get_current_admin)],
    keyword: Annotated[str | None, Query(max_length=128)] = None,
    store_status: Annotated[
        StoreStatus | None,
        Query(alias="status"),
    ] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> StoreAdminListResponse:
    return await StoreService(session).list_admin(
        admin_user=current_admin,
        keyword=keyword,
        status=store_status,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=StoreRead, status_code=status.HTTP_201_CREATED)
async def create_store(
    payload: StoreCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
    current_admin: StoreManager,
) -> StoreRead:
    return await StoreService(session).create(payload, current_admin)


@router.patch("/{store_id}", response_model=StoreRead)
async def update_store(
    store_id: UUID,
    payload: StoreUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
    current_admin: StoreManager,
) -> StoreRead:
    try:
        return await StoreService(session).update(
            store_id,
            payload,
            current_admin,
        )
    except StoreNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="门店不存在",
        ) from error
