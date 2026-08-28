from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.schemas.franchise import FranchisePagePublicRead
from app.services.franchise_service import FranchisePageNotFoundError, FranchiseService

router = APIRouter(prefix="/stores/{store_id}/franchise", tags=["app-franchise"])


@router.get("", response_model=FranchisePagePublicRead)
async def get_franchise_page(
    store_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> FranchisePagePublicRead:
    try:
        return await FranchiseService(session).get_public(store_id)
    except FranchisePageNotFoundError as error:
        raise HTTPException(status_code=404, detail="加盟合作页面暂未发布") from error
