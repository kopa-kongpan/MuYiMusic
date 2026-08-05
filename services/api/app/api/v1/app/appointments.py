from typing import Annotated, NoReturn
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.core.config import get_settings
from app.core.database import get_session
from app.models.appointment import AppointmentStatus
from app.models.user import User
from app.schemas.appointment import (
    AppointmentCancelRequest,
    AppointmentCreate,
    AppointmentListResponse,
    AppointmentRead,
)
from app.services.appointment_service import (
    AppointmentConflictError,
    AppointmentResourceNotFoundError,
    AppointmentService,
    AppointmentValidationError,
)

router = APIRouter(tags=["app-appointments"])
CurrentUser = Annotated[User, Depends(get_current_user)]
IdempotencyKey = Annotated[
    str,
    Header(alias="Idempotency-Key", min_length=8, max_length=128),
]


def handle_appointment_error(error: Exception) -> NoReturn:
    if isinstance(error, AppointmentResourceNotFoundError):
        raise HTTPException(status_code=404, detail="预约资源不存在") from error
    if isinstance(error, AppointmentConflictError):
        raise HTTPException(status_code=409, detail=str(error)) from error
    if isinstance(error, AppointmentValidationError):
        raise HTTPException(status_code=422, detail=str(error)) from error
    raise error


@router.post(
    "/schedules/{schedule_id}/appointments",
    response_model=AppointmentRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_appointment(
    schedule_id: UUID,
    payload: AppointmentCreate,
    idempotency_key: IdempotencyKey,
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AppointmentRead:
    try:
        return await AppointmentService(session, get_settings()).create_appointment(
            user=current_user,
            schedule_id=schedule_id,
            payload=payload,
            idempotency_key=idempotency_key,
        )
    except (
        AppointmentResourceNotFoundError,
        AppointmentConflictError,
        AppointmentValidationError,
    ) as error:
        handle_appointment_error(error)


@router.get("/me/appointments", response_model=AppointmentListResponse)
async def list_my_appointments(
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_session)],
    store_id: UUID | None = None,
    appointment_status: Annotated[
        AppointmentStatus | None,
        Query(alias="status"),
    ] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> AppointmentListResponse:
    return await AppointmentService(session, get_settings()).list_user_appointments(
        user_id=current_user.id,
        store_id=store_id,
        status=appointment_status,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/me/appointments/{appointment_id}/cancel",
    response_model=AppointmentRead,
)
async def cancel_my_appointment(
    appointment_id: UUID,
    payload: AppointmentCancelRequest,
    idempotency_key: IdempotencyKey,
    current_user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AppointmentRead:
    try:
        return await AppointmentService(
            session,
            get_settings(),
        ).cancel_appointment_by_user(
            user=current_user,
            appointment_id=appointment_id,
            payload=payload,
            idempotency_key=idempotency_key,
        )
    except (
        AppointmentResourceNotFoundError,
        AppointmentConflictError,
        AppointmentValidationError,
    ) as error:
        handle_appointment_error(error)
