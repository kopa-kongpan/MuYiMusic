from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.appointment import (
    AppointmentCancelledBy,
    AppointmentStatus,
    ConsumptionKind,
    ConsumptionStatus,
)


class AppointmentCreate(BaseModel):
    entitlement_id: UUID | None = None


class AppointmentCancelRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    reason: str | None = Field(default=None, max_length=500)


class AppointmentAdminCancelRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    reason: str = Field(min_length=1, max_length=500)


class ConsumptionCreateRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    notes: str = Field(default="", max_length=1000)


class ConsumptionReverseRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    reason: str = Field(min_length=1, max_length=500)


class LessonConsumptionRead(BaseModel):
    id: UUID
    appointment_id: UUID
    user_id: UUID
    store_id: UUID
    entitlement_id: UUID
    kind: ConsumptionKind
    status: ConsumptionStatus
    lessons: int
    operator_admin_id: UUID
    notes: str
    created_at: datetime
    reversed_by_admin_id: UUID | None
    reversal_reason: str | None
    reversed_at: datetime | None


class AppointmentRead(BaseModel):
    id: UUID
    appointment_no: str
    user_id: UUID
    user_nickname: str
    store_id: UUID
    schedule_id: UUID
    entitlement_id: UUID
    entitlement_course_name: str
    entitlement_remaining_lessons: int
    entitlement_reserved_lessons: int
    entitlement_available_lessons: int
    teacher_id: UUID
    teacher_name: str
    product_id: UUID | None
    course_name: str
    starts_at: datetime
    ends_at: datetime
    status: AppointmentStatus
    cancelled_by: AppointmentCancelledBy | None
    cancellation_reason: str | None
    cancelled_at: datetime | None
    completed_at: datetime | None
    no_show_at: datetime | None
    active_consumption_id: UUID | None
    booking_closes_at: datetime
    cancellation_closes_at: datetime
    can_user_cancel: bool
    can_admin_settle: bool
    created_at: datetime
    updated_at: datetime


class AppointmentListResponse(BaseModel):
    items: list[AppointmentRead]
    total: int
    page: int
    page_size: int
