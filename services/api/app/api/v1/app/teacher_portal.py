from datetime import datetime
from typing import Annotated, NoReturn
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.api.v1.app.appointments import handle_appointment_error
from app.core.config import get_settings
from app.core.database import get_session
from app.models.appointment import AppointmentStatus
from app.models.user import User
from app.schemas.appointment import (
    AppointmentAdminCancelRequest,
    AppointmentListResponse,
    AppointmentRead,
)
from app.schemas.notification import NotificationListResponse, NotificationRead
from app.schemas.teacher_portal import (
    TeacherBindRequest,
    TeacherIdentityListResponse,
    TeacherIdentityRead,
)
from app.services.appointment_service import (
    AppointmentConflictError,
    AppointmentResourceNotFoundError,
    AppointmentService,
    AppointmentValidationError,
)
from app.services.notification_service import NotificationService
from app.services.teacher_portal_service import (
    TeacherPortalConflictError,
    TeacherPortalNotFoundError,
    TeacherPortalService,
)

router = APIRouter(prefix="/teacher", tags=["app-teacher"])
CurrentUser = Annotated[User, Depends(get_current_user)]
Session = Annotated[AsyncSession, Depends(get_session)]
IdempotencyKey = Annotated[
    str, Header(alias="Idempotency-Key", min_length=8, max_length=128)
]


def handle_teacher_error(error: Exception) -> NoReturn:
    if isinstance(error, TeacherPortalNotFoundError):
        raise HTTPException(status_code=404, detail="教师身份不存在") from error
    if isinstance(error, TeacherPortalConflictError):
        raise HTTPException(status_code=409, detail=str(error)) from error
    raise error


@router.post("/bind", response_model=TeacherIdentityRead)
async def bind_teacher(
    payload: TeacherBindRequest, current_user: CurrentUser, session: Session
) -> TeacherIdentityRead:
    try:
        return await TeacherPortalService(session).bind(
            user=current_user, code=payload.code, provider=payload.provider
        )
    except (TeacherPortalNotFoundError, TeacherPortalConflictError) as error:
        handle_teacher_error(error)


@router.get("/identities", response_model=TeacherIdentityListResponse)
async def teacher_identities(
    current_user: CurrentUser, session: Session
) -> TeacherIdentityListResponse:
    return await TeacherPortalService(session).identities(current_user.id)


@router.get("/{teacher_id}/appointments", response_model=AppointmentListResponse)
async def teacher_appointments(
    teacher_id: UUID,
    starts_from: datetime,
    starts_before: datetime,
    current_user: CurrentUser,
    session: Session,
    appointment_status: Annotated[
        AppointmentStatus | None, Query(alias="status")
    ] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> AppointmentListResponse:
    try:
        return await AppointmentService(
            session, get_settings()
        ).list_teacher_appointments(
            user_id=current_user.id,
            teacher_id=teacher_id,
            starts_from=starts_from,
            starts_before=starts_before,
            status=appointment_status,
            page=page,
            page_size=page_size,
        )
    except TeacherPortalNotFoundError as error:
        handle_teacher_error(error)
    except AppointmentValidationError as error:
        handle_appointment_error(error)


@router.post(
    "/{teacher_id}/appointments/{appointment_id}/cancel",
    response_model=AppointmentRead,
)
async def cancel_teacher_appointment(
    teacher_id: UUID,
    appointment_id: UUID,
    payload: AppointmentAdminCancelRequest,
    idempotency_key: IdempotencyKey,
    current_user: CurrentUser,
    session: Session,
) -> AppointmentRead:
    try:
        return await AppointmentService(
            session, get_settings()
        ).cancel_appointment_by_teacher(
            user_id=current_user.id,
            teacher_id=teacher_id,
            appointment_id=appointment_id,
            payload=payload,
            idempotency_key=idempotency_key,
        )
    except TeacherPortalNotFoundError as error:
        handle_teacher_error(error)
    except (
        AppointmentResourceNotFoundError,
        AppointmentConflictError,
        AppointmentValidationError,
    ) as error:
        handle_appointment_error(error)


@router.get("/{teacher_id}/notifications", response_model=NotificationListResponse)
async def teacher_notifications(
    teacher_id: UUID,
    current_user: CurrentUser,
    session: Session,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> NotificationListResponse:
    try:
        await TeacherPortalService(session).require_teacher(current_user.id, teacher_id)
    except TeacherPortalNotFoundError as error:
        handle_teacher_error(error)
    return await NotificationService(session).list_teacher(teacher_id, page, page_size)


@router.post(
    "/{teacher_id}/notifications/{notification_id}/read",
    response_model=NotificationRead,
)
async def mark_teacher_notification_read(
    teacher_id: UUID,
    notification_id: UUID,
    current_user: CurrentUser,
    session: Session,
) -> NotificationRead:
    try:
        await TeacherPortalService(session).require_teacher(current_user.id, teacher_id)
    except TeacherPortalNotFoundError as error:
        handle_teacher_error(error)
    item = await NotificationService(session).mark_teacher_read(
        teacher_id, notification_id
    )
    if item is None:
        raise HTTPException(status_code=404, detail="消息不存在")
    return item
