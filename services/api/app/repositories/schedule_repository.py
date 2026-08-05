from datetime import datetime
from typing import cast
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.schedule import ClassSchedule, ScheduleStatus, Teacher


class ScheduleRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_teacher(
        self,
        teacher_id: UUID,
        *,
        for_update: bool = False,
    ) -> Teacher | None:
        statement = select(Teacher).where(Teacher.id == teacher_id)
        if for_update:
            statement = statement.with_for_update()
        return cast(Teacher | None, await self.session.scalar(statement))

    async def get_teacher_by_name(
        self,
        store_id: UUID,
        name: str,
    ) -> Teacher | None:
        statement = select(Teacher).where(
            Teacher.store_id == store_id,
            func.lower(Teacher.name) == name.lower(),
        )
        return cast(Teacher | None, await self.session.scalar(statement))

    async def list_teachers(
        self,
        *,
        store_id: UUID,
        keyword: str | None,
        is_active: bool | None,
        page: int,
        page_size: int,
    ) -> tuple[list[Teacher], int]:
        filters = [Teacher.store_id == store_id]
        if keyword:
            pattern = f"%{keyword}%"
            filters.append(
                or_(
                    Teacher.name.ilike(pattern),
                    Teacher.specialties.ilike(pattern),
                )
            )
        if is_active is not None:
            filters.append(Teacher.is_active.is_(is_active))
        total = int(
            await self.session.scalar(select(func.count(Teacher.id)).where(*filters))
            or 0
        )
        statement = (
            select(Teacher)
            .where(*filters)
            .order_by(Teacher.sort_order, Teacher.created_at, Teacher.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list((await self.session.scalars(statement)).all()), total

    def add_teacher(self, teacher: Teacher) -> None:
        self.session.add(teacher)

    async def get_schedule(
        self,
        schedule_id: UUID,
        *,
        for_update: bool = False,
    ) -> ClassSchedule | None:
        statement = (
            select(ClassSchedule)
            .where(ClassSchedule.id == schedule_id)
            .options(selectinload(ClassSchedule.teacher))
        )
        if for_update:
            statement = statement.with_for_update()
        return cast(ClassSchedule | None, await self.session.scalar(statement))

    async def has_teacher_conflict(
        self,
        *,
        teacher_id: UUID,
        starts_at: datetime,
        ends_at: datetime,
        exclude_schedule_id: UUID | None = None,
    ) -> bool:
        filters = [
            ClassSchedule.teacher_id == teacher_id,
            ClassSchedule.status != ScheduleStatus.CANCELLED,
            ClassSchedule.starts_at < ends_at,
            ClassSchedule.ends_at > starts_at,
        ]
        if exclude_schedule_id is not None:
            filters.append(ClassSchedule.id != exclude_schedule_id)
        statement = select(ClassSchedule.id).where(*filters).limit(1)
        return await self.session.scalar(statement) is not None

    async def list_schedules(
        self,
        *,
        store_id: UUID,
        starts_from: datetime,
        starts_before: datetime,
        teacher_id: UUID | None,
        status: ScheduleStatus | None,
        public_only: bool,
        now: datetime,
        page: int,
        page_size: int,
    ) -> tuple[list[ClassSchedule], int]:
        filters = [
            ClassSchedule.store_id == store_id,
            ClassSchedule.starts_at < starts_before,
            ClassSchedule.ends_at > starts_from,
        ]
        if teacher_id is not None:
            filters.append(ClassSchedule.teacher_id == teacher_id)
        if status is not None:
            filters.append(ClassSchedule.status == status)
        if public_only:
            filters.extend(
                (
                    ClassSchedule.status == ScheduleStatus.OPEN,
                    ClassSchedule.ends_at > now,
                    ClassSchedule.reserved_count < ClassSchedule.capacity,
                    Teacher.is_active.is_(True),
                )
            )
        base = select(ClassSchedule).join(
            Teacher,
            Teacher.id == ClassSchedule.teacher_id,
        )
        total = int(
            await self.session.scalar(
                select(func.count(ClassSchedule.id))
                .join(Teacher, Teacher.id == ClassSchedule.teacher_id)
                .where(*filters)
            )
            or 0
        )
        statement = (
            base.options(selectinload(ClassSchedule.teacher))
            .where(*filters)
            .order_by(ClassSchedule.starts_at, ClassSchedule.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list((await self.session.scalars(statement)).all()), total

    def add_schedule(self, schedule: ClassSchedule) -> None:
        self.session.add(schedule)
