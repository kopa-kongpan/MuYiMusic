from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import (
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
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.schedule import ClassSchedule
    from app.models.user import CourseEntitlement, User


class AppointmentStatus(StrEnum):
    RESERVED = "reserved"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    NO_SHOW = "no_show"


class AppointmentCancelledBy(StrEnum):
    USER = "user"
    ADMIN = "admin"
    TEACHER = "teacher"


class ConsumptionKind(StrEnum):
    ATTENDED = "attended"
    NO_SHOW = "no_show"


class ConsumptionStatus(StrEnum):
    APPLIED = "applied"
    REVERSED = "reversed"


class Appointment(Base):
    __tablename__ = "appointments"
    __table_args__ = (
        # 下面两条复合索引在 20260805_0006 迁移里就已建好，这里必须同步声明，
        # 否则 autogenerate 会把它们当成「已移除」而生成 drop_index。
        Index(
            "ix_appointments_user_status_created",
            "user_id",
            "status",
            "created_at",
        ),
        Index(
            "ix_appointments_store_schedule_status",
            "store_id",
            "schedule_id",
            "status",
        ),
        # 管理端列表页（list_admin）：按门店 + 状态筛，
        # 再 created_at DESC, id DESC 分页。
        #
        # 没有这条索引时，查 completed（占全表 96%）只能用 store_id 单列索引
        # 捞出该门店全部 4.4 万行、回表 5414 个块，再排序取 20 条。
        #
        # 列顺序刻意和 ORDER BY 完全一致（含 DESC），这样连排序步骤都省掉，
        # 索引扫描读满 LIMIT 就停；INCLUDE 带上 schedule_id 让分页的
        # count(*) 能走 Index Only Scan（Heap Fetches: 0）。
        #
        # 实测（21.7 万行 / 109MB，各跑 3 次取区间）：
        #   列表    9.7~10.3ms → 0.13~0.31ms
        #   count(*) 11.1~13.8ms → 8.4ms（仍需聚合 4.2 万条匹配行，但不再回表）
        # 索引体积 18MB。
        Index(
            "ix_appointments_store_status_created",
            "store_id",
            "status",
            text("created_at DESC"),
            text("id DESC"),
            postgresql_include=("schedule_id",),
        ),
        UniqueConstraint(
            "user_id",
            "booking_idempotency_key",
            name="uq_appointments_user_booking_key",
        ),
        UniqueConstraint(
            "user_id",
            "cancel_idempotency_key",
            name="uq_appointments_user_cancel_key",
        ),
        Index(
            "uq_appointments_user_schedule_reserved",
            "user_id",
            "schedule_id",
            unique=True,
            postgresql_where=text("status = 'reserved'"),
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    appointment_no: Mapped[str] = mapped_column(String(32), unique=True)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        index=True,
    )
    store_id: Mapped[UUID] = mapped_column(
        ForeignKey("stores.id", ondelete="RESTRICT"),
        index=True,
    )
    schedule_id: Mapped[UUID] = mapped_column(
        ForeignKey("class_schedules.id", ondelete="RESTRICT"),
        index=True,
    )
    entitlement_id: Mapped[UUID] = mapped_column(
        ForeignKey("course_entitlements.id", ondelete="RESTRICT"),
        index=True,
    )
    status: Mapped[AppointmentStatus] = mapped_column(
        Enum(
            AppointmentStatus,
            name="appointment_status",
            values_callable=lambda values: [value.value for value in values],
        ),
        default=AppointmentStatus.RESERVED,
        server_default=AppointmentStatus.RESERVED.value,
        index=True,
    )
    booking_idempotency_key: Mapped[str] = mapped_column(String(128))
    cancel_idempotency_key: Mapped[str | None] = mapped_column(String(128))
    cancelled_by: Mapped[AppointmentCancelledBy | None] = mapped_column(
        Enum(
            AppointmentCancelledBy,
            name="appointment_cancelled_by",
            values_callable=lambda values: [value.value for value in values],
        )
    )
    cancellation_reason: Mapped[str | None] = mapped_column(Text)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    no_show_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
    user: Mapped[User] = relationship(lazy="selectin")
    schedule: Mapped[ClassSchedule] = relationship(lazy="selectin")
    entitlement: Mapped[CourseEntitlement] = relationship(lazy="selectin")
    consumptions: Mapped[list[LessonConsumption]] = relationship(
        back_populates="appointment",
        lazy="selectin",
        order_by="LessonConsumption.created_at",
    )


class LessonConsumption(Base):
    __tablename__ = "lesson_consumptions"
    __table_args__ = (
        CheckConstraint("lessons > 0", name="ck_consumptions_lessons"),
        UniqueConstraint(
            "store_id",
            "idempotency_key",
            name="uq_consumptions_store_key",
        ),
        UniqueConstraint(
            "store_id",
            "reversal_idempotency_key",
            name="uq_consumptions_store_reversal_key",
        ),
        Index(
            "uq_consumptions_appointment_applied",
            "appointment_id",
            unique=True,
            postgresql_where=text("status = 'applied'"),
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    appointment_id: Mapped[UUID] = mapped_column(
        ForeignKey("appointments.id", ondelete="RESTRICT"),
        index=True,
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        index=True,
    )
    store_id: Mapped[UUID] = mapped_column(
        ForeignKey("stores.id", ondelete="RESTRICT"),
        index=True,
    )
    entitlement_id: Mapped[UUID] = mapped_column(
        ForeignKey("course_entitlements.id", ondelete="RESTRICT"),
        index=True,
    )
    kind: Mapped[ConsumptionKind] = mapped_column(
        Enum(
            ConsumptionKind,
            name="consumption_kind",
            values_callable=lambda values: [value.value for value in values],
        )
    )
    status: Mapped[ConsumptionStatus] = mapped_column(
        Enum(
            ConsumptionStatus,
            name="consumption_status",
            values_callable=lambda values: [value.value for value in values],
        ),
        default=ConsumptionStatus.APPLIED,
        server_default=ConsumptionStatus.APPLIED.value,
        index=True,
    )
    lessons: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    operator_admin_id: Mapped[UUID] = mapped_column(
        ForeignKey("admin_users.id", ondelete="RESTRICT"),
        index=True,
    )
    idempotency_key: Mapped[str] = mapped_column(String(128))
    notes: Mapped[str] = mapped_column(Text, default="", server_default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    reversed_by_admin_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("admin_users.id", ondelete="RESTRICT"),
        index=True,
    )
    reversal_idempotency_key: Mapped[str | None] = mapped_column(String(128))
    reversal_reason: Mapped[str | None] = mapped_column(Text)
    reversed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    appointment: Mapped[Appointment] = relationship(back_populates="consumptions")
    entitlement: Mapped[CourseEntitlement] = relationship(lazy="selectin")
