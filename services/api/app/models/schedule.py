from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ScheduleStatus(StrEnum):
    OPEN = "open"
    CLOSED = "closed"
    CANCELLED = "cancelled"


class Teacher(Base):
    __tablename__ = "teachers"
    __table_args__ = (
        Index("ix_teachers_store_active_order", "store_id", "is_active", "sort_order"),
        UniqueConstraint("store_id", "name", name="uq_teachers_store_name"),
        CheckConstraint("sort_order >= 0", name="ck_teachers_sort_order"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    store_id: Mapped[UUID] = mapped_column(
        ForeignKey("stores.id", ondelete="CASCADE"),
        index=True,
    )
    name: Mapped[str] = mapped_column(String(128))
    specialties: Mapped[str] = mapped_column(Text, default="", server_default="")
    bio: Mapped[str] = mapped_column(Text, default="", server_default="")
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default="true",
        index=True,
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
    schedules: Mapped[list["ClassSchedule"]] = relationship(back_populates="teacher")


class ClassSchedule(Base):
    __tablename__ = "class_schedules"
    __table_args__ = (
        Index("ix_schedules_store_start_status", "store_id", "starts_at", "status"),
        Index("ix_schedules_teacher_time", "teacher_id", "starts_at", "ends_at"),
        CheckConstraint("ends_at > starts_at", name="ck_schedules_time_window"),
        CheckConstraint("capacity > 0", name="ck_schedules_capacity"),
        CheckConstraint(
            "reserved_count >= 0 AND reserved_count <= capacity",
            name="ck_schedules_reserved_count",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    store_id: Mapped[UUID] = mapped_column(
        ForeignKey("stores.id", ondelete="CASCADE"),
        index=True,
    )
    teacher_id: Mapped[UUID] = mapped_column(
        ForeignKey("teachers.id", ondelete="RESTRICT"),
        index=True,
    )
    product_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("products.id", ondelete="SET NULL"),
        index=True,
    )
    course_name: Mapped[str] = mapped_column(String(128))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    capacity: Mapped[int] = mapped_column(Integer)
    reserved_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default="0",
    )
    status: Mapped[ScheduleStatus] = mapped_column(
        Enum(
            ScheduleStatus,
            name="schedule_status",
            values_callable=lambda values: [value.value for value in values],
        ),
        default=ScheduleStatus.OPEN,
        server_default=ScheduleStatus.OPEN.value,
        index=True,
    )
    notes: Mapped[str] = mapped_column(Text, default="", server_default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
    teacher: Mapped[Teacher] = relationship(back_populates="schedules")
