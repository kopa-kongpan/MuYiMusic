from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.schemas.schedule import SchedulePublicListResponse
from app.services.schedule_service import (
    ScheduleResourceNotFoundError,
    ScheduleService,
    ScheduleValidationError,
)

router = APIRouter(prefix="/stores/{store_id}/schedules", tags=["app-schedules"])


@router.get("", response_model=SchedulePublicListResponse)
async def list_schedules(
    store_id: UUID,
    starts_from: datetime,
    starts_before: datetime,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> SchedulePublicListResponse:
    try:
        return await ScheduleService(session).list_schedules_public(
            store_id=store_id,
            starts_from=starts_from,
            starts_before=starts_before,
        )
    except ScheduleResourceNotFoundError as error:
        raise HTTPException(status_code=404, detail="门店不存在或已停用") from error
    except ScheduleValidationError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
