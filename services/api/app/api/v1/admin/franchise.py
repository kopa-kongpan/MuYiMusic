from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import require_permission
from app.core.database import get_session
from app.models.admin import AdminUser
from app.schemas.franchise import FranchisePageRead, FranchisePageUpdate
from app.services.franchise_service import FranchisePageNotFoundError, FranchiseService

router = APIRouter(prefix="/stores/{store_id}/franchise", tags=["admin-franchise"])
FranchiseManager = Annotated[
    AdminUser, Depends(require_permission("store_content:manage"))
]


@router.get("", response_model=FranchisePageRead | None)
async def get_franchise_page(
    store_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    current_admin: FranchiseManager,
) -> FranchisePageRead | None:
    try:
        return await FranchiseService(session).get_admin(store_id, current_admin)
    except FranchisePageNotFoundError as error:
        raise HTTPException(status_code=404, detail="门店不存在") from error


@router.put("", response_model=FranchisePageRead)
async def update_franchise_page(
    store_id: UUID,
    payload: FranchisePageUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
    current_admin: FranchiseManager,
) -> FranchisePageRead:
    try:
        return await FranchiseService(session).upsert(store_id, payload, current_admin)
    except FranchisePageNotFoundError as error:
        raise HTTPException(status_code=404, detail="门店不存在") from error
