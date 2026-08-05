from datetime import datetime
from typing import Annotated, NoReturn
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import require_permission
from app.core.config import get_settings
from app.core.database import get_session
from app.models.admin import AdminUser
from app.models.appointment import AppointmentStatus
from app.schemas.appointment import (
    AppointmentAdminCancelRequest,
    AppointmentListResponse,
    AppointmentRead,
    ConsumptionCreateRequest,
    ConsumptionReverseRequest,
)
from app.services.appointment_service import (
    AppointmentConflictError,
    AppointmentResourceNotFoundError,
    AppointmentService,
    AppointmentValidationError,
)

router = APIRouter(prefix="/stores/{store_id}", tags=["admin-appointments"])
AppointmentManager = Annotated[
    AdminUser,
    Depends(require_permission("appointments:manage")),
]
ConsumptionManager = Annotated[
    AdminUser,
    Depends(require_permission("consumptions:manage")),
]
ConsumptionReverser = Annotated[
    AdminUser,
    Depends(require_permission("consumptions:reverse")),
]
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


@router.get("/appointments", response_model=AppointmentListResponse)
async def list_appointments(
    store_id: UUID,
    starts_from: datetime,
    starts_before: datetime,
    session: Annotated[AsyncSession, Depends(get_session)],
    current_admin: AppointmentManager,
    appointment_status: Annotated[
        AppointmentStatus | None,
        Query(alias="status"),
    ] = None,
    keyword: Annotated[str | None, Query(max_length=128)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> AppointmentListResponse:
    try:
        return await AppointmentService(
            session,
            get_settings(),
        ).list_admin_appointments(
            store_id=store_id,
            admin_user=current_admin,
            starts_from=starts_from,
            starts_before=starts_before,
            status=appointment_status,
            keyword=keyword,
            page=page,
            page_size=page_size,
        )
    except (
        AppointmentResourceNotFoundError,
        AppointmentConflictError,
        AppointmentValidationError,
    ) as error:
        handle_appointment_error(error)


@router.post(
    "/appointments/{appointment_id}/cancel",
    response_model=AppointmentRead,
)
async def cancel_appointment(
    store_id: UUID,
    appointment_id: UUID,
    payload: AppointmentAdminCancelRequest,
    idempotency_key: IdempotencyKey,
    session: Annotated[AsyncSession, Depends(get_session)],
    current_admin: AppointmentManager,
) -> AppointmentRead:
    try:
        return await AppointmentService(
            session,
            get_settings(),
        ).cancel_appointment_by_admin(
            store_id=store_id,
            appointment_id=appointment_id,
            payload=payload,
            idempotency_key=idempotency_key,
            admin_user=current_admin,
        )
    except (
        AppointmentResourceNotFoundError,
        AppointmentConflictError,
        AppointmentValidationError,
    ) as error:
        handle_appointment_error(error)


@router.post(
    "/appointments/{appointment_id}/consume",
    response_model=AppointmentRead,
)
async def consume_appointment(
    store_id: UUID,
    appointment_id: UUID,
    payload: ConsumptionCreateRequest,
    idempotency_key: IdempotencyKey,
    session: Annotated[AsyncSession, Depends(get_session)],
    current_admin: ConsumptionManager,
) -> AppointmentRead:
    try:
        return await AppointmentService(session, get_settings()).consume_appointment(
            store_id=store_id,
            appointment_id=appointment_id,
            payload=payload,
            idempotency_key=idempotency_key,
            admin_user=current_admin,
        )
    except (
        AppointmentResourceNotFoundError,
        AppointmentConflictError,
        AppointmentValidationError,
    ) as error:
        handle_appointment_error(error)


@router.post(
    "/appointments/{appointment_id}/no-show",
    response_model=AppointmentRead,
)
async def mark_no_show(
    store_id: UUID,
    appointment_id: UUID,
    payload: ConsumptionCreateRequest,
    idempotency_key: IdempotencyKey,
    session: Annotated[AsyncSession, Depends(get_session)],
    current_admin: ConsumptionManager,
) -> AppointmentRead:
    try:
        return await AppointmentService(session, get_settings()).mark_no_show(
            store_id=store_id,
            appointment_id=appointment_id,
            payload=payload,
            idempotency_key=idempotency_key,
            admin_user=current_admin,
        )
    except (
        AppointmentResourceNotFoundError,
        AppointmentConflictError,
        AppointmentValidationError,
    ) as error:
        handle_appointment_error(error)


@router.post(
    "/consumptions/{consumption_id}/reverse",
    response_model=AppointmentRead,
)
async def reverse_consumption(
    store_id: UUID,
    consumption_id: UUID,
    payload: ConsumptionReverseRequest,
    idempotency_key: IdempotencyKey,
    session: Annotated[AsyncSession, Depends(get_session)],
    current_admin: ConsumptionReverser,
) -> AppointmentRead:
    try:
        return await AppointmentService(session, get_settings()).reverse_consumption(
            store_id=store_id,
            consumption_id=consumption_id,
            payload=payload,
            idempotency_key=idempotency_key,
            admin_user=current_admin,
        )
    except (
        AppointmentResourceNotFoundError,
        AppointmentConflictError,
        AppointmentValidationError,
    ) as error:
        handle_appointment_error(error)
