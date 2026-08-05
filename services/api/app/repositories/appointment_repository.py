from datetime import datetime
from typing import cast
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.sql.base import ExecutableOption
from sqlalchemy.sql.elements import ColumnElement

from app.models.appointment import (
    Appointment,
    AppointmentStatus,
    LessonConsumption,
)
from app.models.schedule import ClassSchedule
from app.models.user import CourseEntitlement, EntitlementStatus, User


def appointment_load_options() -> tuple[
    ExecutableOption,
    ExecutableOption,
    ExecutableOption,
    ExecutableOption,
]:
    return (
        selectinload(Appointment.user),
        selectinload(Appointment.schedule).selectinload(ClassSchedule.teacher),
        selectinload(Appointment.entitlement),
        selectinload(Appointment.consumptions),
    )


class AppointmentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def lock_user(self, user_id: UUID) -> User | None:
        statement = select(User).where(User.id == user_id).with_for_update()
        return cast(User | None, await self.session.scalar(statement))

    async def get_by_booking_key(
        self,
        user_id: UUID,
        idempotency_key: str,
    ) -> Appointment | None:
        statement = (
            select(Appointment)
            .where(
                Appointment.user_id == user_id,
                Appointment.booking_idempotency_key == idempotency_key,
            )
            .options(*appointment_load_options())
        )
        return cast(Appointment | None, await self.session.scalar(statement))

    async def get_appointment(
        self,
        appointment_id: UUID,
        *,
        for_update: bool = False,
    ) -> Appointment | None:
        statement = (
            select(Appointment)
            .where(Appointment.id == appointment_id)
            .options(*appointment_load_options())
        )
        if for_update:
            statement = statement.with_for_update()
        return cast(Appointment | None, await self.session.scalar(statement))

    async def get_schedule_for_update(
        self,
        schedule_id: UUID,
    ) -> ClassSchedule | None:
        statement = (
            select(ClassSchedule)
            .where(ClassSchedule.id == schedule_id)
            .options(selectinload(ClassSchedule.teacher))
            .with_for_update()
        )
        return cast(ClassSchedule | None, await self.session.scalar(statement))

    async def get_entitlement_for_update(
        self,
        entitlement_id: UUID,
    ) -> CourseEntitlement | None:
        statement = (
            select(CourseEntitlement)
            .where(CourseEntitlement.id == entitlement_id)
            .with_for_update()
        )
        return cast(CourseEntitlement | None, await self.session.scalar(statement))

    async def find_bookable_entitlement_for_update(
        self,
        *,
        user_id: UUID,
        store_id: UUID,
        product_id: UUID,
        starts_at: datetime,
    ) -> CourseEntitlement | None:
        statement = (
            select(CourseEntitlement)
            .where(
                CourseEntitlement.user_id == user_id,
                CourseEntitlement.store_id == store_id,
                CourseEntitlement.product_id == product_id,
                CourseEntitlement.status == EntitlementStatus.ACTIVE,
                CourseEntitlement.valid_from <= starts_at,
                or_(
                    CourseEntitlement.expires_at.is_(None),
                    CourseEntitlement.expires_at > starts_at,
                ),
                CourseEntitlement.remaining_lessons
                > CourseEntitlement.reserved_lessons,
            )
            .order_by(
                CourseEntitlement.expires_at.asc().nulls_last(),
                CourseEntitlement.created_at,
                CourseEntitlement.id,
            )
            .limit(1)
            .with_for_update()
        )
        return cast(CourseEntitlement | None, await self.session.scalar(statement))

    async def has_overlapping_reservation(
        self,
        *,
        user_id: UUID,
        starts_at: datetime,
        ends_at: datetime,
    ) -> bool:
        statement = (
            select(Appointment.id)
            .join(ClassSchedule, ClassSchedule.id == Appointment.schedule_id)
            .where(
                Appointment.user_id == user_id,
                Appointment.status == AppointmentStatus.RESERVED,
                ClassSchedule.starts_at < ends_at,
                ClassSchedule.ends_at > starts_at,
            )
            .limit(1)
        )
        return await self.session.scalar(statement) is not None

    async def list_user(
        self,
        *,
        user_id: UUID,
        store_id: UUID | None,
        status: AppointmentStatus | None,
        page: int,
        page_size: int,
    ) -> tuple[list[Appointment], int]:
        filters: list[ColumnElement[bool]] = [Appointment.user_id == user_id]
        if store_id is not None:
            filters.append(Appointment.store_id == store_id)
        if status is not None:
            filters.append(Appointment.status == status)
        return await self._list(filters=filters, page=page, page_size=page_size)

    async def list_admin(
        self,
        *,
        store_id: UUID,
        starts_from: datetime,
        starts_before: datetime,
        status: AppointmentStatus | None,
        keyword: str | None,
        page: int,
        page_size: int,
    ) -> tuple[list[Appointment], int]:
        filters: list[ColumnElement[bool]] = [
            Appointment.store_id == store_id,
            ClassSchedule.starts_at < starts_before,
            ClassSchedule.ends_at > starts_from,
        ]
        if status is not None:
            filters.append(Appointment.status == status)
        if keyword:
            pattern = f"%{keyword}%"
            filters.append(
                or_(
                    Appointment.appointment_no.ilike(pattern),
                    User.nickname.ilike(pattern),
                    User.phone.ilike(pattern),
                )
            )
        return await self._list(
            filters=filters,
            page=page,
            page_size=page_size,
            join_schedule=True,
            join_user=True,
        )

    async def _list(
        self,
        *,
        filters: list[ColumnElement[bool]],
        page: int,
        page_size: int,
        join_schedule: bool = False,
        join_user: bool = False,
    ) -> tuple[list[Appointment], int]:
        count_statement = select(func.count(Appointment.id))
        list_statement = select(Appointment)
        if join_schedule:
            count_statement = count_statement.join(
                ClassSchedule,
                ClassSchedule.id == Appointment.schedule_id,
            )
            list_statement = list_statement.join(
                ClassSchedule,
                ClassSchedule.id == Appointment.schedule_id,
            )
        if join_user:
            count_statement = count_statement.join(User, User.id == Appointment.user_id)
            list_statement = list_statement.join(User, User.id == Appointment.user_id)
        total = int(await self.session.scalar(count_statement.where(*filters)) or 0)
        list_statement = (
            list_statement.where(*filters)
            .options(*appointment_load_options())
            .order_by(Appointment.created_at.desc(), Appointment.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        items = list((await self.session.scalars(list_statement)).unique().all())
        return items, total

    async def get_consumption_by_key(
        self,
        store_id: UUID,
        idempotency_key: str,
    ) -> LessonConsumption | None:
        statement = select(LessonConsumption).where(
            LessonConsumption.store_id == store_id,
            LessonConsumption.idempotency_key == idempotency_key,
        )
        return cast(LessonConsumption | None, await self.session.scalar(statement))

    async def get_consumption_by_reversal_key(
        self,
        store_id: UUID,
        idempotency_key: str,
    ) -> LessonConsumption | None:
        statement = select(LessonConsumption).where(
            LessonConsumption.store_id == store_id,
            LessonConsumption.reversal_idempotency_key == idempotency_key,
        )
        return cast(LessonConsumption | None, await self.session.scalar(statement))

    async def get_consumption(
        self,
        consumption_id: UUID,
        *,
        for_update: bool = False,
    ) -> LessonConsumption | None:
        statement = (
            select(LessonConsumption)
            .where(LessonConsumption.id == consumption_id)
            .options(
                selectinload(LessonConsumption.entitlement),
                selectinload(LessonConsumption.appointment)
                .selectinload(Appointment.schedule)
                .selectinload(ClassSchedule.teacher),
                selectinload(LessonConsumption.appointment).selectinload(
                    Appointment.user
                ),
                selectinload(LessonConsumption.appointment).selectinload(
                    Appointment.entitlement
                ),
                selectinload(LessonConsumption.appointment).selectinload(
                    Appointment.consumptions
                ),
            )
        )
        if for_update:
            statement = statement.with_for_update()
        return cast(LessonConsumption | None, await self.session.scalar(statement))

    def add_appointment(self, appointment: Appointment) -> None:
        self.session.add(appointment)

    def add_consumption(self, consumption: LessonConsumption) -> None:
        self.session.add(consumption)
