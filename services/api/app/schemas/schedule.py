from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.schedule import ScheduleStatus


class TeacherCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=128)
    specialties: str = Field(default="", max_length=1000)
    bio: str = Field(default="", max_length=4000)
    is_active: bool = True
    sort_order: int = Field(default=0, ge=0, le=1_000_000)


class TeacherUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str | None = Field(default=None, min_length=1, max_length=128)
    specialties: str | None = Field(default=None, max_length=1000)
    bio: str | None = Field(default=None, max_length=4000)
    is_active: bool | None = None
    sort_order: int | None = Field(default=None, ge=0, le=1_000_000)


class TeacherRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    store_id: UUID
    name: str
    specialties: str
    bio: str
    is_active: bool
    sort_order: int
    created_at: datetime
    updated_at: datetime


class TeacherListResponse(BaseModel):
    items: list[TeacherRead]
    total: int
    page: int
    page_size: int


class ScheduleCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    teacher_id: UUID
    product_id: UUID | None = None
    course_name: str | None = Field(default=None, min_length=1, max_length=128)
    starts_at: datetime
    ends_at: datetime
    capacity: int = Field(ge=1, le=200)
    notes: str = Field(default="", max_length=2000)

    @model_validator(mode="after")
    def validate_time_window(self) -> "ScheduleCreate":
        validate_aware_window(self.starts_at, self.ends_at)
        if self.product_id is None and not self.course_name:
            raise ValueError("课程商品和课程名称至少填写一项")
        return self


class ScheduleUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    teacher_id: UUID | None = None
    product_id: UUID | None = None
    course_name: str | None = Field(default=None, min_length=1, max_length=128)
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    capacity: int | None = Field(default=None, ge=1, le=200)
    notes: str | None = Field(default=None, max_length=2000)


class ScheduleStatusUpdate(BaseModel):
    status: ScheduleStatus


class ScheduleRead(BaseModel):
    id: UUID
    store_id: UUID
    teacher_id: UUID
    teacher_name: str
    product_id: UUID | None
    course_name: str
    starts_at: datetime
    ends_at: datetime
    capacity: int
    reserved_count: int
    available_slots: int
    status: ScheduleStatus
    notes: str
    created_at: datetime
    updated_at: datetime


class SchedulePublicRead(BaseModel):
    id: UUID
    store_id: UUID
    teacher_id: UUID
    teacher_name: str
    product_id: UUID | None
    course_name: str
    starts_at: datetime
    ends_at: datetime
    capacity: int
    reserved_count: int
    available_slots: int


class ScheduleListResponse(BaseModel):
    items: list[ScheduleRead]
    total: int
    page: int
    page_size: int


class SchedulePublicListResponse(BaseModel):
    items: list[SchedulePublicRead]
    total: int


def validate_aware_window(starts_at: datetime, ends_at: datetime) -> None:
    if starts_at.tzinfo is None or ends_at.tzinfo is None:
        raise ValueError("排课时间必须包含时区")
    if ends_at <= starts_at:
        raise ValueError("结束时间必须晚于开始时间")
