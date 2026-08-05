from datetime import datetime
from typing import Annotated, NoReturn
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import require_permission
from app.core.database import get_session
from app.models.admin import AdminUser
from app.models.schedule import ScheduleStatus
from app.schemas.schedule import (
    ScheduleCreate,
    ScheduleListResponse,
    ScheduleRead,
    ScheduleStatusUpdate,
    ScheduleUpdate,
    TeacherCreate,
    TeacherListResponse,
    TeacherRead,
    TeacherUpdate,
)
from app.services.schedule_service import (
    ScheduleConflictError,
    ScheduleResourceNotFoundError,
    ScheduleService,
    ScheduleValidationError,
)

router = APIRouter(prefix="/stores/{store_id}", tags=["admin-schedules"])
ScheduleManager = Annotated[
    AdminUser,
    Depends(require_permission("schedules:manage")),
]


def handle_schedule_error(error: Exception) -> NoReturn:
    if isinstance(error, ScheduleResourceNotFoundError):
        raise HTTPException(status_code=404, detail="排课资源不存在") from error
    if isinstance(error, ScheduleConflictError):
        raise HTTPException(status_code=409, detail=str(error)) from error
    if isinstance(error, ScheduleValidationError):
        raise HTTPException(status_code=422, detail=str(error)) from error
    raise error


@router.get("/teachers", response_model=TeacherListResponse)
async def list_teachers(
    store_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    current_admin: ScheduleManager,
    keyword: Annotated[str | None, Query(max_length=128)] = None,
    is_active: bool | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> TeacherListResponse:
    try:
        return await ScheduleService(session).list_teachers_admin(
            store_id=store_id,
            admin_user=current_admin,
            keyword=keyword,
            is_active=is_active,
            page=page,
            page_size=page_size,
        )
    except (
        ScheduleResourceNotFoundError,
        ScheduleConflictError,
        ScheduleValidationError,
    ) as error:
        handle_schedule_error(error)


@router.post(
    "/teachers",
    response_model=TeacherRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_teacher(
    store_id: UUID,
    payload: TeacherCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
    current_admin: ScheduleManager,
) -> TeacherRead:
    try:
        return await ScheduleService(session).create_teacher(
            store_id=store_id,
            payload=payload,
            admin_user=current_admin,
        )
    except (
        ScheduleResourceNotFoundError,
        ScheduleConflictError,
        ScheduleValidationError,
    ) as error:
        handle_schedule_error(error)


@router.patch("/teachers/{teacher_id}", response_model=TeacherRead)
async def update_teacher(
    store_id: UUID,
    teacher_id: UUID,
    payload: TeacherUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
    current_admin: ScheduleManager,
) -> TeacherRead:
    try:
        return await ScheduleService(session).update_teacher(
            store_id=store_id,
            teacher_id=teacher_id,
            payload=payload,
            admin_user=current_admin,
        )
    except (
        ScheduleResourceNotFoundError,
        ScheduleConflictError,
        ScheduleValidationError,
    ) as error:
        handle_schedule_error(error)


@router.get("/schedules", response_model=ScheduleListResponse)
async def list_schedules(
    store_id: UUID,
    starts_from: datetime,
    starts_before: datetime,
    session: Annotated[AsyncSession, Depends(get_session)],
    current_admin: ScheduleManager,
    teacher_id: UUID | None = None,
    schedule_status: Annotated[
        ScheduleStatus | None,
        Query(alias="status"),
    ] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ScheduleListResponse:
    try:
        return await ScheduleService(session).list_schedules_admin(
            store_id=store_id,
            admin_user=current_admin,
            starts_from=starts_from,
            starts_before=starts_before,
            teacher_id=teacher_id,
            status=schedule_status,
            page=page,
            page_size=page_size,
        )
    except (
        ScheduleResourceNotFoundError,
        ScheduleConflictError,
        ScheduleValidationError,
    ) as error:
        handle_schedule_error(error)


@router.post(
    "/schedules",
    response_model=ScheduleRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_schedule(
    store_id: UUID,
    payload: ScheduleCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
    current_admin: ScheduleManager,
) -> ScheduleRead:
    try:
        return await ScheduleService(session).create_schedule(
            store_id=store_id,
            payload=payload,
            admin_user=current_admin,
        )
    except (
        ScheduleResourceNotFoundError,
        ScheduleConflictError,
        ScheduleValidationError,
    ) as error:
        handle_schedule_error(error)


@router.patch("/schedules/{schedule_id}", response_model=ScheduleRead)
async def update_schedule(
    store_id: UUID,
    schedule_id: UUID,
    payload: ScheduleUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
    current_admin: ScheduleManager,
) -> ScheduleRead:
    try:
        return await ScheduleService(session).update_schedule(
            store_id=store_id,
            schedule_id=schedule_id,
            payload=payload,
            admin_user=current_admin,
        )
    except (
        ScheduleResourceNotFoundError,
        ScheduleConflictError,
        ScheduleValidationError,
    ) as error:
        handle_schedule_error(error)


@router.post(
    "/schedules/{schedule_id}/status",
    response_model=ScheduleRead,
)
async def change_schedule_status(
    store_id: UUID,
    schedule_id: UUID,
    payload: ScheduleStatusUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
    current_admin: ScheduleManager,
) -> ScheduleRead:
    try:
        return await ScheduleService(session).change_schedule_status(
            store_id=store_id,
            schedule_id=schedule_id,
            payload=payload,
            admin_user=current_admin,
        )
    except (
        ScheduleResourceNotFoundError,
        ScheduleConflictError,
        ScheduleValidationError,
    ) as error:
        handle_schedule_error(error)
