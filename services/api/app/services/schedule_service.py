from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.admin import AdminUser
from app.models.product import Product, ProductStatus
from app.models.schedule import ClassSchedule, ScheduleStatus, Teacher
from app.models.store import StoreStatus
from app.repositories.audit_repository import AuditRepository
from app.repositories.product_repository import ProductRepository
from app.repositories.schedule_repository import ScheduleRepository
from app.repositories.store_repository import StoreRepository
from app.schemas.schedule import (
    ScheduleCreate,
    ScheduleListResponse,
    SchedulePublicListResponse,
    SchedulePublicRead,
    ScheduleRead,
    ScheduleStatusUpdate,
    ScheduleUpdate,
    TeacherCreate,
    TeacherListResponse,
    TeacherRead,
    TeacherUpdate,
    validate_aware_window,
)
from app.services.store_service import can_access_store


class ScheduleResourceNotFoundError(Exception):
    pass


class ScheduleConflictError(Exception):
    pass


class ScheduleValidationError(Exception):
    pass


def teacher_snapshot(teacher: Teacher) -> dict[str, Any]:
    return {
        "store_id": str(teacher.store_id),
        "name": teacher.name,
        "specialties": teacher.specialties,
        "bio": teacher.bio,
        "is_active": teacher.is_active,
        "sort_order": teacher.sort_order,
    }


def schedule_snapshot(schedule: ClassSchedule) -> dict[str, Any]:
    return {
        "store_id": str(schedule.store_id),
        "teacher_id": str(schedule.teacher_id),
        "product_id": str(schedule.product_id) if schedule.product_id else None,
        "course_name": schedule.course_name,
        "starts_at": schedule.starts_at.isoformat(),
        "ends_at": schedule.ends_at.isoformat(),
        "capacity": schedule.capacity,
        "reserved_count": schedule.reserved_count,
        "status": schedule.status.value,
        "notes": schedule.notes,
    }


class ScheduleService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = ScheduleRepository(session)
        self.store_repository = StoreRepository(session)
        self.product_repository = ProductRepository(session)
        self.audit_repository = AuditRepository(session)
        self.settings = get_settings()

    async def list_teachers_admin(
        self,
        *,
        store_id: UUID,
        admin_user: AdminUser,
        keyword: str | None,
        is_active: bool | None,
        page: int,
        page_size: int,
    ) -> TeacherListResponse:
        await self._require_store_access(store_id, admin_user)
        teachers, total = await self.repository.list_teachers(
            store_id=store_id,
            keyword=keyword,
            is_active=is_active,
            page=page,
            page_size=page_size,
        )
        return TeacherListResponse(
            items=[TeacherRead.model_validate(item) for item in teachers],
            total=total,
            page=page,
            page_size=page_size,
        )

    async def create_teacher(
        self,
        *,
        store_id: UUID,
        payload: TeacherCreate,
        admin_user: AdminUser,
    ) -> TeacherRead:
        await self._require_store_access(store_id, admin_user)
        if await self.repository.get_teacher_by_name(store_id, payload.name):
            raise ScheduleConflictError("当前门店已存在同名教师")
        teacher = Teacher(store_id=store_id, **payload.model_dump())
        try:
            self.repository.add_teacher(teacher)
            await self.session.flush()
            self.audit_repository.add(
                admin_user_id=admin_user.id,
                action="teacher.create",
                resource_type="teacher",
                resource_id=str(teacher.id),
                details={"after": teacher_snapshot(teacher)},
            )
            await self.session.commit()
        except IntegrityError as error:
            await self.session.rollback()
            raise ScheduleConflictError("当前门店已存在同名教师") from error
        except Exception:
            await self.session.rollback()
            raise
        await self.session.refresh(teacher)
        return TeacherRead.model_validate(teacher)

    async def update_teacher(
        self,
        *,
        store_id: UUID,
        teacher_id: UUID,
        payload: TeacherUpdate,
        admin_user: AdminUser,
    ) -> TeacherRead:
        await self._require_store_access(store_id, admin_user)
        teacher = await self.repository.get_teacher(teacher_id)
        if teacher is None or teacher.store_id != store_id:
            raise ScheduleResourceNotFoundError
        changes = payload.model_dump(exclude_unset=True, exclude_none=True)
        if not changes:
            return TeacherRead.model_validate(teacher)
        if "name" in changes:
            duplicate = await self.repository.get_teacher_by_name(
                store_id,
                str(changes["name"]),
            )
            if duplicate is not None and duplicate.id != teacher.id:
                raise ScheduleConflictError("当前门店已存在同名教师")
        before = teacher_snapshot(teacher)
        for field, value in changes.items():
            setattr(teacher, field, value)
        try:
            await self.session.flush()
            self.audit_repository.add(
                admin_user_id=admin_user.id,
                action="teacher.update",
                resource_type="teacher",
                resource_id=str(teacher.id),
                details={"before": before, "after": teacher_snapshot(teacher)},
            )
            await self.session.commit()
        except IntegrityError as error:
            await self.session.rollback()
            raise ScheduleConflictError("当前门店已存在同名教师") from error
        except Exception:
            await self.session.rollback()
            raise
        await self.session.refresh(teacher)
        return TeacherRead.model_validate(teacher)

    async def list_schedules_admin(
        self,
        *,
        store_id: UUID,
        admin_user: AdminUser,
        starts_from: datetime,
        starts_before: datetime,
        teacher_id: UUID | None,
        status: ScheduleStatus | None,
        page: int,
        page_size: int,
    ) -> ScheduleListResponse:
        await self._require_store_access(store_id, admin_user)
        self._validate_query_window(starts_from, starts_before)
        schedules, total = await self.repository.list_schedules(
            store_id=store_id,
            starts_from=starts_from,
            starts_before=starts_before,
            teacher_id=teacher_id,
            status=status,
            public_only=False,
            now=datetime.now(UTC),
            page=page,
            page_size=page_size,
        )
        return ScheduleListResponse(
            items=[self._schedule_read(item) for item in schedules],
            total=total,
            page=page,
            page_size=page_size,
        )

    async def list_schedules_public(
        self,
        *,
        store_id: UUID,
        starts_from: datetime,
        starts_before: datetime,
        page: int,
        page_size: int,
    ) -> SchedulePublicListResponse:
        store = await self.store_repository.get(store_id)
        if store is None or store.status != StoreStatus.ACTIVE:
            raise ScheduleResourceNotFoundError
        self._validate_query_window(starts_from, starts_before)
        now = datetime.now(UTC)
        schedules, total = await self.repository.list_schedules(
            store_id=store_id,
            starts_from=starts_from,
            starts_before=starts_before,
            teacher_id=None,
            status=None,
            public_only=True,
            now=now,
            page=page,
            page_size=page_size,
        )
        return SchedulePublicListResponse(
            items=[self._schedule_public_read(item, now) for item in schedules],
            total=total,
            page=page,
            page_size=page_size,
        )

    async def create_schedule(
        self,
        *,
        store_id: UUID,
        payload: ScheduleCreate,
        admin_user: AdminUser,
    ) -> ScheduleRead:
        await self._require_store_access(store_id, admin_user)
        self._validate_future_window(payload.starts_at, payload.ends_at)
        teacher = await self._require_teacher(
            store_id,
            payload.teacher_id,
            for_update=True,
        )
        product = await self._optional_product(store_id, payload.product_id)
        course_name = product.name if product else payload.course_name
        if not course_name:
            raise ScheduleValidationError("请填写课程名称")
        if await self.repository.has_teacher_conflict(
            teacher_id=teacher.id,
            starts_at=payload.starts_at,
            ends_at=payload.ends_at,
        ):
            raise ScheduleConflictError("该教师在所选时间已有排课")
        schedule = ClassSchedule(
            store_id=store_id,
            teacher_id=teacher.id,
            product_id=product.id if product else None,
            course_name=course_name,
            starts_at=payload.starts_at,
            ends_at=payload.ends_at,
            capacity=payload.capacity,
            notes=payload.notes,
            teacher=teacher,
        )
        try:
            self.repository.add_schedule(schedule)
            await self.session.flush()
            self.audit_repository.add(
                admin_user_id=admin_user.id,
                action="schedule.create",
                resource_type="class_schedule",
                resource_id=str(schedule.id),
                details={"after": schedule_snapshot(schedule)},
            )
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise
        await self.session.refresh(schedule)
        return self._schedule_read(schedule)

    async def update_schedule(
        self,
        *,
        store_id: UUID,
        schedule_id: UUID,
        payload: ScheduleUpdate,
        admin_user: AdminUser,
    ) -> ScheduleRead:
        await self._require_store_access(store_id, admin_user)
        schedule = await self.repository.get_schedule(schedule_id, for_update=True)
        if schedule is None or schedule.store_id != store_id:
            raise ScheduleResourceNotFoundError
        if schedule.status == ScheduleStatus.CANCELLED:
            raise ScheduleConflictError("已取消排课不可编辑")
        changes = payload.model_dump(exclude_unset=True)
        if not changes:
            return self._schedule_read(schedule)
        protected_fields = {
            "teacher_id",
            "product_id",
            "starts_at",
            "ends_at",
            "capacity",
        }
        if schedule.reserved_count > 0 and protected_fields.intersection(changes):
            raise ScheduleConflictError("已有预约时只能修改课程名称和到课说明")
        teacher_id = payload.teacher_id or schedule.teacher_id
        teacher = await self._require_teacher(
            store_id,
            teacher_id,
            for_update=True,
        )
        starts_at = payload.starts_at or schedule.starts_at
        ends_at = payload.ends_at or schedule.ends_at
        self._validate_future_window(starts_at, ends_at)
        capacity = payload.capacity or schedule.capacity
        if capacity < schedule.reserved_count:
            raise ScheduleConflictError("容量不能小于已预约人数")
        if await self.repository.has_teacher_conflict(
            teacher_id=teacher.id,
            starts_at=starts_at,
            ends_at=ends_at,
            exclude_schedule_id=schedule.id,
        ):
            raise ScheduleConflictError("该教师在所选时间已有排课")
        product_id = (
            payload.product_id if "product_id" in changes else schedule.product_id
        )
        product = await self._optional_product(
            store_id,
            product_id,
            require_published="product_id" in changes,
        )
        course_name = (
            product.name if product else payload.course_name or schedule.course_name
        )
        before = schedule_snapshot(schedule)
        schedule.teacher_id = teacher.id
        schedule.teacher = teacher
        schedule.product_id = product.id if product else None
        schedule.course_name = course_name
        schedule.starts_at = starts_at
        schedule.ends_at = ends_at
        schedule.capacity = capacity
        if payload.notes is not None:
            schedule.notes = payload.notes
        try:
            await self.session.flush()
            self.audit_repository.add(
                admin_user_id=admin_user.id,
                action="schedule.update",
                resource_type="class_schedule",
                resource_id=str(schedule.id),
                details={"before": before, "after": schedule_snapshot(schedule)},
            )
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise
        await self.session.refresh(schedule)
        return self._schedule_read(schedule)

    async def change_schedule_status(
        self,
        *,
        store_id: UUID,
        schedule_id: UUID,
        payload: ScheduleStatusUpdate,
        admin_user: AdminUser,
    ) -> ScheduleRead:
        await self._require_store_access(store_id, admin_user)
        schedule = await self.repository.get_schedule(schedule_id, for_update=True)
        if schedule is None or schedule.store_id != store_id:
            raise ScheduleResourceNotFoundError
        if payload.status == schedule.status:
            return self._schedule_read(schedule)
        allowed = {
            ScheduleStatus.OPEN: {ScheduleStatus.CLOSED, ScheduleStatus.CANCELLED},
            ScheduleStatus.CLOSED: {ScheduleStatus.OPEN, ScheduleStatus.CANCELLED},
            ScheduleStatus.CANCELLED: set(),
        }
        if payload.status not in allowed[schedule.status]:
            raise ScheduleConflictError("不允许执行该排课状态变更")
        if payload.status == ScheduleStatus.CANCELLED and schedule.reserved_count > 0:
            raise ScheduleConflictError("已有预约的排课需先处理受影响用户")
        before = schedule_snapshot(schedule)
        schedule.status = payload.status
        try:
            await self.session.flush()
            self.audit_repository.add(
                admin_user_id=admin_user.id,
                action="schedule.status_change",
                resource_type="class_schedule",
                resource_id=str(schedule.id),
                details={"before": before, "after": schedule_snapshot(schedule)},
            )
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise
        await self.session.refresh(schedule)
        return self._schedule_read(schedule)

    async def _require_store_access(
        self,
        store_id: UUID,
        admin_user: AdminUser,
    ) -> None:
        if not can_access_store(admin_user, store_id):
            raise ScheduleResourceNotFoundError
        if await self.store_repository.get(store_id) is None:
            raise ScheduleResourceNotFoundError

    async def _require_teacher(
        self,
        store_id: UUID,
        teacher_id: UUID,
        *,
        for_update: bool,
    ) -> Teacher:
        teacher = await self.repository.get_teacher(
            teacher_id,
            for_update=for_update,
        )
        if teacher is None or teacher.store_id != store_id:
            raise ScheduleValidationError("教师不属于当前门店")
        if not teacher.is_active:
            raise ScheduleValidationError("停用教师不能新增或调整排课")
        return teacher

    async def _optional_product(
        self,
        store_id: UUID,
        product_id: UUID | None,
        *,
        require_published: bool = True,
    ) -> Product | None:
        if product_id is None:
            return None
        product = await self.product_repository.get_product(product_id)
        if product is None or product.store_id != store_id:
            raise ScheduleValidationError("课程商品不属于当前门店")
        if require_published and product.status != ProductStatus.PUBLISHED:
            raise ScheduleValidationError("只能为已发布课程商品创建排课")
        return product

    @staticmethod
    def _validate_future_window(starts_at: datetime, ends_at: datetime) -> None:
        try:
            validate_aware_window(starts_at, ends_at)
        except ValueError as error:
            raise ScheduleValidationError(str(error)) from error
        if starts_at <= datetime.now(UTC):
            raise ScheduleValidationError("排课开始时间必须晚于当前时间")

    @staticmethod
    def _validate_query_window(
        starts_from: datetime,
        starts_before: datetime,
    ) -> None:
        try:
            validate_aware_window(starts_from, starts_before)
        except ValueError as error:
            raise ScheduleValidationError(str(error)) from error
        if starts_before - starts_from > timedelta(days=31):
            raise ScheduleValidationError("单次最多查询 31 天排课")

    @staticmethod
    def _schedule_read(schedule: ClassSchedule) -> ScheduleRead:
        return ScheduleRead(
            id=schedule.id,
            store_id=schedule.store_id,
            teacher_id=schedule.teacher_id,
            teacher_name=schedule.teacher.name,
            product_id=schedule.product_id,
            course_name=schedule.course_name,
            starts_at=schedule.starts_at,
            ends_at=schedule.ends_at,
            capacity=schedule.capacity,
            reserved_count=schedule.reserved_count,
            available_slots=schedule.capacity - schedule.reserved_count,
            status=schedule.status,
            notes=schedule.notes,
            created_at=schedule.created_at,
            updated_at=schedule.updated_at,
        )

    def _schedule_public_read(
        self,
        schedule: ClassSchedule,
        now: datetime,
    ) -> SchedulePublicRead:
        booking_closes_at = schedule.starts_at - timedelta(
            minutes=self.settings.booking_cutoff_minutes
        )
        return SchedulePublicRead(
            id=schedule.id,
            store_id=schedule.store_id,
            teacher_id=schedule.teacher_id,
            teacher_name=schedule.teacher.name,
            product_id=schedule.product_id,
            course_name=schedule.course_name,
            starts_at=schedule.starts_at,
            ends_at=schedule.ends_at,
            capacity=schedule.capacity,
            reserved_count=schedule.reserved_count,
            available_slots=schedule.capacity - schedule.reserved_count,
            booking_closes_at=booking_closes_at,
            is_booking_open=(
                schedule.product_id is not None
                and schedule.reserved_count < schedule.capacity
                and now <= booking_closes_at
            ),
        )
