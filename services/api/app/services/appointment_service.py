from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models.admin import AdminUser
from app.models.appointment import (
    Appointment,
    AppointmentCancelledBy,
    AppointmentStatus,
    ConsumptionKind,
    ConsumptionStatus,
    LessonConsumption,
)
from app.models.schedule import ClassSchedule, ScheduleStatus
from app.models.user import CourseEntitlement, EntitlementStatus, User
from app.repositories.appointment_repository import AppointmentRepository
from app.repositories.audit_repository import AuditRepository
from app.repositories.store_repository import StoreRepository
from app.schemas.appointment import (
    AppointmentAdminCancelRequest,
    AppointmentCancelRequest,
    AppointmentCreate,
    AppointmentListResponse,
    AppointmentRead,
    ConsumptionCreateRequest,
    ConsumptionReverseRequest,
)
from app.services.entitlement_service import sync_entitlement_status
from app.services.store_service import can_access_store


class AppointmentResourceNotFoundError(Exception):
    pass


class AppointmentConflictError(Exception):
    pass


class AppointmentValidationError(Exception):
    pass


class AppointmentService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings
        self.repository = AppointmentRepository(session)
        self.store_repository = StoreRepository(session)
        self.audit_repository = AuditRepository(session)

    async def create_appointment(
        self,
        *,
        user: User,
        schedule_id: UUID,
        payload: AppointmentCreate,
        idempotency_key: str,
    ) -> AppointmentRead:
        now = datetime.now(UTC)
        locked_user = await self.repository.lock_user(user.id)
        if locked_user is None:
            raise AppointmentResourceNotFoundError
        existing = await self.repository.get_by_booking_key(
            user.id,
            idempotency_key,
        )
        if existing is not None:
            if existing.schedule_id != schedule_id:
                raise AppointmentConflictError("幂等键已用于其他排课")
            return self._to_read(existing, now)

        schedule = await self.repository.get_schedule_for_update(schedule_id)
        if schedule is None or schedule.status != ScheduleStatus.OPEN:
            raise AppointmentResourceNotFoundError
        if not schedule.teacher.is_active:
            raise AppointmentConflictError("授课教师当前不可预约")
        if schedule.product_id is None:
            raise AppointmentConflictError("该排课未关联可用课程权益")
        if now > self._booking_closes_at(schedule):
            raise AppointmentConflictError("已超过开课前 2 小时的预约截止时间")
        if schedule.reserved_count >= schedule.capacity:
            raise AppointmentConflictError("当前排课名额已满")
        if await self.repository.has_overlapping_reservation(
            user_id=user.id,
            starts_at=schedule.starts_at,
            ends_at=schedule.ends_at,
        ):
            raise AppointmentConflictError("你在该时段已有其他预约")

        entitlement = await self._lock_bookable_entitlement(
            user_id=user.id,
            schedule=schedule,
            entitlement_id=payload.entitlement_id,
        )
        appointment = Appointment(
            appointment_no=self._appointment_no(now),
            user=locked_user,
            user_id=user.id,
            store_id=schedule.store_id,
            schedule=schedule,
            schedule_id=schedule.id,
            entitlement=entitlement,
            entitlement_id=entitlement.id,
            booking_idempotency_key=idempotency_key,
        )
        schedule.reserved_count += 1
        entitlement.reserved_lessons += 1
        try:
            self.repository.add_appointment(appointment)
            await self.session.commit()
        except IntegrityError as error:
            await self.session.rollback()
            raise AppointmentConflictError("预约请求冲突，请刷新后重试") from error
        except Exception:
            await self.session.rollback()
            raise
        return self._to_read(await self._reload_appointment(appointment.id), now)

    async def cancel_appointment_by_user(
        self,
        *,
        user: User,
        appointment_id: UUID,
        payload: AppointmentCancelRequest,
        idempotency_key: str,
    ) -> AppointmentRead:
        appointment, schedule, entitlement = await self._lock_appointment_graph(
            appointment_id
        )
        if appointment.user_id != user.id:
            raise AppointmentResourceNotFoundError
        now = datetime.now(UTC)
        if appointment.status == AppointmentStatus.CANCELLED:
            return self._to_read(appointment, now)
        if appointment.status != AppointmentStatus.RESERVED:
            raise AppointmentConflictError("当前预约状态不允许取消")
        if now > self._cancellation_closes_at(schedule):
            raise AppointmentConflictError("已超过开课前 2 小时的取消截止时间")
        return await self._cancel_locked(
            appointment=appointment,
            schedule=schedule,
            entitlement=entitlement,
            cancelled_by=AppointmentCancelledBy.USER,
            reason=payload.reason,
            idempotency_key=idempotency_key,
            admin_user=None,
            now=now,
        )

    async def cancel_appointment_by_admin(
        self,
        *,
        store_id: UUID,
        appointment_id: UUID,
        payload: AppointmentAdminCancelRequest,
        idempotency_key: str,
        admin_user: AdminUser,
    ) -> AppointmentRead:
        await self._require_store_access(store_id, admin_user)
        appointment, schedule, entitlement = await self._lock_appointment_graph(
            appointment_id
        )
        if appointment.store_id != store_id:
            raise AppointmentResourceNotFoundError
        now = datetime.now(UTC)
        if appointment.status == AppointmentStatus.CANCELLED:
            return self._to_read(appointment, now)
        if appointment.status != AppointmentStatus.RESERVED:
            raise AppointmentConflictError("当前预约状态不允许取消")
        return await self._cancel_locked(
            appointment=appointment,
            schedule=schedule,
            entitlement=entitlement,
            cancelled_by=AppointmentCancelledBy.ADMIN,
            reason=payload.reason,
            idempotency_key=idempotency_key,
            admin_user=admin_user,
            now=now,
        )

    async def list_user_appointments(
        self,
        *,
        user_id: UUID,
        store_id: UUID | None,
        status: AppointmentStatus | None,
        page: int,
        page_size: int,
    ) -> AppointmentListResponse:
        appointments, total = await self.repository.list_user(
            user_id=user_id,
            store_id=store_id,
            status=status,
            page=page,
            page_size=page_size,
        )
        now = datetime.now(UTC)
        return AppointmentListResponse(
            items=[self._to_read(item, now) for item in appointments],
            total=total,
            page=page,
            page_size=page_size,
        )

    async def list_admin_appointments(
        self,
        *,
        store_id: UUID,
        admin_user: AdminUser,
        starts_from: datetime,
        starts_before: datetime,
        status: AppointmentStatus | None,
        keyword: str | None,
        page: int,
        page_size: int,
    ) -> AppointmentListResponse:
        await self._require_store_access(store_id, admin_user)
        self._validate_query_window(starts_from, starts_before)
        appointments, total = await self.repository.list_admin(
            store_id=store_id,
            starts_from=starts_from,
            starts_before=starts_before,
            status=status,
            keyword=keyword,
            page=page,
            page_size=page_size,
        )
        now = datetime.now(UTC)
        return AppointmentListResponse(
            items=[self._to_read(item, now) for item in appointments],
            total=total,
            page=page,
            page_size=page_size,
        )

    async def consume_appointment(
        self,
        *,
        store_id: UUID,
        appointment_id: UUID,
        payload: ConsumptionCreateRequest,
        idempotency_key: str,
        admin_user: AdminUser,
    ) -> AppointmentRead:
        return await self._settle_appointment(
            store_id=store_id,
            appointment_id=appointment_id,
            payload=payload,
            idempotency_key=idempotency_key,
            admin_user=admin_user,
            kind=ConsumptionKind.ATTENDED,
        )

    async def mark_no_show(
        self,
        *,
        store_id: UUID,
        appointment_id: UUID,
        payload: ConsumptionCreateRequest,
        idempotency_key: str,
        admin_user: AdminUser,
    ) -> AppointmentRead:
        return await self._settle_appointment(
            store_id=store_id,
            appointment_id=appointment_id,
            payload=payload,
            idempotency_key=idempotency_key,
            admin_user=admin_user,
            kind=ConsumptionKind.NO_SHOW,
        )

    async def reverse_consumption(
        self,
        *,
        store_id: UUID,
        consumption_id: UUID,
        payload: ConsumptionReverseRequest,
        idempotency_key: str,
        admin_user: AdminUser,
    ) -> AppointmentRead:
        await self._require_store_access(store_id, admin_user)
        preliminary = await self.repository.get_consumption(consumption_id)
        if preliminary is None or preliminary.store_id != store_id:
            raise AppointmentResourceNotFoundError
        appointment, _, entitlement = await self._lock_appointment_graph(
            preliminary.appointment_id
        )
        existing = await self.repository.get_consumption_by_reversal_key(
            store_id,
            idempotency_key,
        )
        if existing is not None:
            if existing.id != consumption_id:
                raise AppointmentConflictError("幂等键已用于其他撤销操作")
            return self._to_read(appointment, datetime.now(UTC))
        consumption = await self.repository.get_consumption(
            consumption_id,
            for_update=True,
        )
        if consumption is None or consumption.status != ConsumptionStatus.APPLIED:
            raise AppointmentConflictError("该消课记录已撤销或不可撤销")
        if appointment.status not in {
            AppointmentStatus.COMPLETED,
            AppointmentStatus.NO_SHOW,
        }:
            raise AppointmentConflictError("预约状态与消课记录不一致")
        now = datetime.now(UTC)
        entitlement.remaining_lessons += consumption.lessons
        entitlement.reserved_lessons += consumption.lessons
        sync_entitlement_status(entitlement, now)
        appointment.status = AppointmentStatus.RESERVED
        appointment.completed_at = None
        appointment.no_show_at = None
        consumption.status = ConsumptionStatus.REVERSED
        consumption.reversed_by_admin_id = admin_user.id
        consumption.reversal_idempotency_key = idempotency_key
        consumption.reversal_reason = payload.reason
        consumption.reversed_at = now
        try:
            await self.session.flush()
            self.audit_repository.add(
                admin_user_id=admin_user.id,
                action="consumption.reverse",
                resource_type="lesson_consumption",
                resource_id=str(consumption.id),
                details={
                    "appointment_id": str(appointment.id),
                    "reason": payload.reason,
                    "restored_lessons": consumption.lessons,
                },
            )
            await self.session.commit()
        except IntegrityError as error:
            await self.session.rollback()
            raise AppointmentConflictError("撤销请求冲突，请刷新后重试") from error
        except Exception:
            await self.session.rollback()
            raise
        return self._to_read(await self._reload_appointment(appointment.id), now)

    async def _settle_appointment(
        self,
        *,
        store_id: UUID,
        appointment_id: UUID,
        payload: ConsumptionCreateRequest,
        idempotency_key: str,
        admin_user: AdminUser,
        kind: ConsumptionKind,
    ) -> AppointmentRead:
        await self._require_store_access(store_id, admin_user)
        appointment, schedule, entitlement = await self._lock_appointment_graph(
            appointment_id
        )
        if appointment.store_id != store_id:
            raise AppointmentResourceNotFoundError
        existing = await self.repository.get_consumption_by_key(
            store_id,
            idempotency_key,
        )
        if existing is not None:
            if existing.appointment_id != appointment_id or existing.kind != kind:
                raise AppointmentConflictError("幂等键已用于其他消课操作")
            return self._to_read(appointment, datetime.now(UTC))
        if appointment.status != AppointmentStatus.RESERVED:
            raise AppointmentConflictError("当前预约状态不允许消课")
        now = datetime.now(UTC)
        if schedule.ends_at > now:
            raise AppointmentConflictError("课程结束后才能执行消课或缺席")
        if entitlement.reserved_lessons < 1 or entitlement.remaining_lessons < 1:
            raise AppointmentConflictError("课程权益锁定课时不足")
        entitlement.reserved_lessons -= 1
        entitlement.remaining_lessons -= 1
        sync_entitlement_status(entitlement, now)
        if kind == ConsumptionKind.ATTENDED:
            appointment.status = AppointmentStatus.COMPLETED
            appointment.completed_at = now
        else:
            appointment.status = AppointmentStatus.NO_SHOW
            appointment.no_show_at = now
        consumption = LessonConsumption(
            appointment=appointment,
            appointment_id=appointment.id,
            user_id=appointment.user_id,
            store_id=appointment.store_id,
            entitlement=entitlement,
            entitlement_id=entitlement.id,
            kind=kind,
            lessons=1,
            operator_admin_id=admin_user.id,
            idempotency_key=idempotency_key,
            notes=payload.notes,
        )
        try:
            self.repository.add_consumption(consumption)
            await self.session.flush()
            self.audit_repository.add(
                admin_user_id=admin_user.id,
                action=(
                    "appointment.consume"
                    if kind == ConsumptionKind.ATTENDED
                    else "appointment.no_show"
                ),
                resource_type="appointment",
                resource_id=str(appointment.id),
                details={
                    "consumption_id": str(consumption.id),
                    "deducted_lessons": 1,
                    "notes": payload.notes,
                },
            )
            await self.session.commit()
        except IntegrityError as error:
            await self.session.rollback()
            raise AppointmentConflictError("消课请求冲突，请刷新后重试") from error
        except Exception:
            await self.session.rollback()
            raise
        return self._to_read(await self._reload_appointment(appointment.id), now)

    async def _cancel_locked(
        self,
        *,
        appointment: Appointment,
        schedule: ClassSchedule,
        entitlement: CourseEntitlement,
        cancelled_by: AppointmentCancelledBy,
        reason: str | None,
        idempotency_key: str,
        admin_user: AdminUser | None,
        now: datetime,
    ) -> AppointmentRead:
        if schedule.reserved_count < 1 or entitlement.reserved_lessons < 1:
            raise AppointmentConflictError("预约名额或锁定课时数据不一致")
        schedule.reserved_count -= 1
        entitlement.reserved_lessons -= 1
        appointment.status = AppointmentStatus.CANCELLED
        appointment.cancel_idempotency_key = idempotency_key
        appointment.cancelled_by = cancelled_by
        appointment.cancellation_reason = reason
        appointment.cancelled_at = now
        try:
            await self.session.flush()
            if admin_user is not None:
                self.audit_repository.add(
                    admin_user_id=admin_user.id,
                    action="appointment.cancel",
                    resource_type="appointment",
                    resource_id=str(appointment.id),
                    details={"reason": reason or ""},
                )
            await self.session.commit()
        except IntegrityError as error:
            await self.session.rollback()
            raise AppointmentConflictError("取消请求冲突，请刷新后重试") from error
        except Exception:
            await self.session.rollback()
            raise
        return self._to_read(await self._reload_appointment(appointment.id), now)

    async def _lock_appointment_graph(
        self,
        appointment_id: UUID,
    ) -> tuple[Appointment, ClassSchedule, CourseEntitlement]:
        preliminary = await self.repository.get_appointment(appointment_id)
        if preliminary is None:
            raise AppointmentResourceNotFoundError
        if await self.repository.lock_user(preliminary.user_id) is None:
            raise AppointmentResourceNotFoundError
        appointment = await self.repository.get_appointment(
            appointment_id,
            for_update=True,
        )
        if appointment is None:
            raise AppointmentResourceNotFoundError
        schedule = await self.repository.get_schedule_for_update(
            appointment.schedule_id
        )
        entitlement = await self.repository.get_entitlement_for_update(
            appointment.entitlement_id
        )
        if schedule is None or entitlement is None:
            raise AppointmentResourceNotFoundError
        return appointment, schedule, entitlement

    async def _lock_bookable_entitlement(
        self,
        *,
        user_id: UUID,
        schedule: ClassSchedule,
        entitlement_id: UUID | None,
    ) -> CourseEntitlement:
        if schedule.product_id is None:
            raise AppointmentConflictError("该排课未关联课程商品")
        entitlement = (
            await self.repository.get_entitlement_for_update(entitlement_id)
            if entitlement_id is not None
            else await self.repository.find_bookable_entitlement_for_update(
                user_id=user_id,
                store_id=schedule.store_id,
                product_id=schedule.product_id,
                starts_at=schedule.starts_at,
            )
        )
        if entitlement is None:
            raise AppointmentConflictError("没有可用于该课程的有效课时")
        if (
            entitlement.user_id != user_id
            or entitlement.store_id != schedule.store_id
            or entitlement.product_id != schedule.product_id
            or entitlement.status != EntitlementStatus.ACTIVE
            or entitlement.valid_from > schedule.starts_at
            or (
                entitlement.expires_at is not None
                and entitlement.expires_at <= schedule.starts_at
            )
            or entitlement.remaining_lessons <= entitlement.reserved_lessons
        ):
            raise AppointmentConflictError("所选课程权益不可用于该排课")
        return entitlement

    async def _reload_appointment(self, appointment_id: UUID) -> Appointment:
        appointment = await self.repository.get_appointment(appointment_id)
        if appointment is None:
            raise AppointmentResourceNotFoundError
        return appointment

    async def _require_store_access(
        self,
        store_id: UUID,
        admin_user: AdminUser,
    ) -> None:
        if not can_access_store(admin_user, store_id):
            raise AppointmentResourceNotFoundError
        if await self.store_repository.get(store_id) is None:
            raise AppointmentResourceNotFoundError

    def _booking_closes_at(self, schedule: ClassSchedule) -> datetime:
        return schedule.starts_at - timedelta(
            minutes=self.settings.booking_cutoff_minutes
        )

    def _cancellation_closes_at(self, schedule: ClassSchedule) -> datetime:
        return schedule.starts_at - timedelta(
            minutes=self.settings.cancellation_cutoff_minutes
        )

    @staticmethod
    def _appointment_no(now: datetime) -> str:
        return f"A{now:%Y%m%d%H%M%S}{uuid4().hex[:12].upper()}"

    @staticmethod
    def _validate_query_window(starts_from: datetime, starts_before: datetime) -> None:
        if starts_from.tzinfo is None or starts_before.tzinfo is None:
            raise AppointmentValidationError("查询时间必须包含时区")
        if starts_before <= starts_from:
            raise AppointmentValidationError("查询结束时间必须晚于开始时间")
        if starts_before - starts_from > timedelta(days=31):
            raise AppointmentValidationError("单次最多查询 31 天预约")

    def _to_read(self, appointment: Appointment, now: datetime) -> AppointmentRead:
        active_consumption = next(
            (
                item
                for item in reversed(appointment.consumptions)
                if item.status == ConsumptionStatus.APPLIED
            ),
            None,
        )
        schedule = appointment.schedule
        entitlement = appointment.entitlement
        return AppointmentRead(
            id=appointment.id,
            appointment_no=appointment.appointment_no,
            user_id=appointment.user_id,
            user_nickname=appointment.user.nickname,
            store_id=appointment.store_id,
            schedule_id=appointment.schedule_id,
            entitlement_id=appointment.entitlement_id,
            entitlement_course_name=entitlement.course_name,
            entitlement_remaining_lessons=entitlement.remaining_lessons,
            entitlement_reserved_lessons=entitlement.reserved_lessons,
            entitlement_available_lessons=(
                entitlement.remaining_lessons - entitlement.reserved_lessons
            ),
            teacher_id=schedule.teacher_id,
            teacher_name=schedule.teacher.name,
            product_id=schedule.product_id,
            course_name=schedule.course_name,
            starts_at=schedule.starts_at,
            ends_at=schedule.ends_at,
            status=appointment.status,
            cancelled_by=appointment.cancelled_by,
            cancellation_reason=appointment.cancellation_reason,
            cancelled_at=appointment.cancelled_at,
            completed_at=appointment.completed_at,
            no_show_at=appointment.no_show_at,
            active_consumption_id=(
                active_consumption.id if active_consumption is not None else None
            ),
            booking_closes_at=self._booking_closes_at(schedule),
            cancellation_closes_at=self._cancellation_closes_at(schedule),
            can_user_cancel=(
                appointment.status == AppointmentStatus.RESERVED
                and now <= self._cancellation_closes_at(schedule)
            ),
            can_admin_settle=(
                appointment.status == AppointmentStatus.RESERVED
                and schedule.ends_at <= now
            ),
            created_at=appointment.created_at,
            updated_at=appointment.updated_at,
        )
