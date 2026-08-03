from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.schemas.store import StorePublicListResponse
from app.services.store_service import StoreService

router = APIRouter(prefix="/stores", tags=["app-stores"])


@router.get("", response_model=StorePublicListResponse)
async def list_stores(
    session: Annotated[AsyncSession, Depends(get_session)],
    keyword: str | None = Query(default=None, max_length=128),
    latitude: float | None = Query(default=None, ge=-90, le=90),
    longitude: float | None = Query(default=None, ge=-180, le=180),
) -> StorePublicListResponse:
    return await StoreService(session).list_public(
        keyword=keyword,
        latitude=latitude,
        longitude=longitude,
    )
