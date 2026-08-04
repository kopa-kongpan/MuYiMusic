from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.providers.object_storage import ObjectStorageProvider, get_object_storage
from app.schemas.store_content import StoreHomeResponse
from app.services.store_content_service import (
    PublicStoreNotFoundError,
    StoreContentService,
)

router = APIRouter(prefix="/stores", tags=["app-store-home"])


@router.get("/{store_id}/home", response_model=StoreHomeResponse)
async def get_store_home(
    store_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    storage: Annotated[ObjectStorageProvider, Depends(get_object_storage)],
) -> StoreHomeResponse:
    try:
        return await StoreContentService(session, storage).get_public_home(store_id)
    except PublicStoreNotFoundError as error:
        raise HTTPException(status_code=404, detail="门店不存在或已停用") from error
