from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import require_permission
from app.core.database import get_session
from app.models.admin import AdminUser
from app.models.store_content import ContentBlockStatus, ContentBlockType
from app.providers.object_storage import ObjectStorageProvider, get_object_storage
from app.schemas.store_content import (
    ContentBlockAdminListResponse,
    ContentBlockCreate,
    ContentBlockRead,
    ContentBlockUpdate,
    ContentOrderUpdate,
)
from app.services.store_content_service import (
    ContentBlockNotFoundError,
    InvalidContentBlockError,
    InvalidContentOrderError,
    StoreContentService,
)

router = APIRouter(
    prefix="/stores/{store_id}/home-content",
    tags=["admin-store-content"],
)
ContentManager = Annotated[
    AdminUser,
    Depends(require_permission("store_content:manage")),
]
StorageDependency = Annotated[ObjectStorageProvider, Depends(get_object_storage)]


@router.get("", response_model=ContentBlockAdminListResponse)
async def list_content(
    store_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    storage: StorageDependency,
    current_admin: ContentManager,
    block_type: Annotated[ContentBlockType | None, Query()] = None,
    content_status: Annotated[
        ContentBlockStatus | None,
        Query(alias="status"),
    ] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ContentBlockAdminListResponse:
    try:
        return await StoreContentService(session, storage).list_admin(
            store_id=store_id,
            admin_user=current_admin,
            block_type=block_type,
            status=content_status,
            page=page,
            page_size=page_size,
        )
    except ContentBlockNotFoundError as error:
        raise HTTPException(status_code=404, detail="门店不存在") from error


@router.post("", response_model=ContentBlockRead, status_code=status.HTTP_201_CREATED)
async def create_content(
    store_id: UUID,
    payload: ContentBlockCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
    storage: StorageDependency,
    current_admin: ContentManager,
) -> ContentBlockRead:
    try:
        return await StoreContentService(session, storage).create(
            store_id=store_id,
            payload=payload,
            admin_user=current_admin,
        )
    except ContentBlockNotFoundError as error:
        raise HTTPException(status_code=404, detail="门店不存在") from error
    except InvalidContentBlockError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.put("/order", response_model=list[ContentBlockRead])
async def reorder_content(
    store_id: UUID,
    payload: ContentOrderUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
    storage: StorageDependency,
    current_admin: ContentManager,
) -> list[ContentBlockRead]:
    try:
        return await StoreContentService(session, storage).reorder(
            store_id=store_id,
            payload=payload,
            admin_user=current_admin,
        )
    except ContentBlockNotFoundError as error:
        raise HTTPException(status_code=404, detail="门店不存在") from error
    except InvalidContentOrderError as error:
        raise HTTPException(status_code=409, detail="排序内容不属于当前门店") from error


@router.patch("/{content_id}", response_model=ContentBlockRead)
async def update_content(
    store_id: UUID,
    content_id: UUID,
    payload: ContentBlockUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
    storage: StorageDependency,
    current_admin: ContentManager,
) -> ContentBlockRead:
    try:
        return await StoreContentService(session, storage).update(
            store_id=store_id,
            content_id=content_id,
            payload=payload,
            admin_user=current_admin,
        )
    except ContentBlockNotFoundError as error:
        raise HTTPException(status_code=404, detail="首页内容不存在") from error
    except InvalidContentBlockError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
