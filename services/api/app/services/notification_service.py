from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.appointment import Appointment, AppointmentStatus
from app.models.notification import (
    Notification,
    NotificationChannel,
    NotificationOutbox,
    NotificationRecipientType,
    NotificationSubscription,
)
from app.models.schedule import ClassSchedule
from app.schemas.notification import (
    NotificationListResponse,
    NotificationRead,
    SubscriptionUpdate,
)


class NotificationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def add_appointment_notification(
        self,
        *,
        appointment: Appointment,
        kind: str,
        recipient_type: NotificationRecipientType,
        title: str,
        content: str,
        template_key: str,
    ) -> Notification:
        suffix = (
            "student" if recipient_type == NotificationRecipientType.USER else "teacher"
        )
        notification_id = uuid4()
        notification = Notification(
            id=notification_id,
            event_key=f"{kind}:{appointment.id}:{suffix}",
            recipient_type=recipient_type,
            recipient_user_id=appointment.user_id
            if recipient_type == NotificationRecipientType.USER
            else None,
            recipient_teacher_id=appointment.schedule.teacher_id
            if recipient_type == NotificationRecipientType.TEACHER
            else None,
            kind=kind,
            title=title,
            content=content,
            appointment_id=appointment.id,
            page_path=(
                "pages/teacher-portal/index"
                if recipient_type == NotificationRecipientType.TEACHER
                else "pages/my-bookings/index"
            ),
            payload={
                "appointment_no": appointment.appointment_no,
                "course_name": appointment.schedule.course_name,
                "starts_at": appointment.schedule.starts_at.isoformat(),
                "teacher_name": appointment.schedule.teacher.name,
                "student_name": appointment.user.nickname,
                "note": "请提前安排时间",
            },
        )
        self.session.add(notification)
        self.session.add(
            NotificationOutbox(
                notification_id=notification_id,
                channel=NotificationChannel.WECHAT_SUBSCRIBE,
                template_key=template_key,
            )
        )
        return notification

    async def list_user(
        self, user_id: UUID, page: int, page_size: int
    ) -> NotificationListResponse:
        filters = (
            Notification.recipient_user_id == user_id,
            Notification.recipient_type == NotificationRecipientType.USER,
        )
        total = int(
            await self.session.scalar(
                select(func.count(Notification.id)).where(*filters)
            )
            or 0
        )
        unread = int(
            await self.session.scalar(
                select(func.count(Notification.id)).where(
                    *filters, Notification.read_at.is_(None)
                )
            )
            or 0
        )
        items = list(
            (
                await self.session.scalars(
                    select(Notification)
                    .where(*filters)
                    .order_by(Notification.created_at.desc())
                    .offset((page - 1) * page_size)
                    .limit(page_size)
                )
            ).all()
        )
        return NotificationListResponse(
            items=[self._read(item) for item in items],
            total=total,
            unread_count=unread,
            page=page,
            page_size=page_size,
        )

    async def list_teacher(
        self, teacher_id: UUID, page: int, page_size: int
    ) -> NotificationListResponse:
        filters = (
            Notification.recipient_teacher_id == teacher_id,
            Notification.recipient_type == NotificationRecipientType.TEACHER,
        )
        total = int(
            await self.session.scalar(
                select(func.count(Notification.id)).where(*filters)
            )
            or 0
        )
        unread = int(
            await self.session.scalar(
                select(func.count(Notification.id)).where(
                    *filters, Notification.read_at.is_(None)
                )
            )
            or 0
        )
        items = list(
            (
                await self.session.scalars(
                    select(Notification)
                    .where(*filters)
                    .order_by(Notification.created_at.desc())
                    .offset((page - 1) * page_size)
                    .limit(page_size)
                )
            ).all()
        )
        return NotificationListResponse(
            items=[self._read(item) for item in items],
            total=total,
            unread_count=unread,
            page=page,
            page_size=page_size,
        )

    async def mark_teacher_read(
        self, teacher_id: UUID, notification_id: UUID
    ) -> NotificationRead | None:
        item = await self.session.scalar(
            select(Notification).where(
                Notification.id == notification_id,
                Notification.recipient_teacher_id == teacher_id,
            )
        )
        if item is None:
            return None
        if item.read_at is None:
            item.read_at = datetime.now(UTC)
            await self.session.commit()
        return self._read(item)

    async def mark_read(
        self, user_id: UUID, notification_id: UUID
    ) -> NotificationRead | None:
        item = await self.session.scalar(
            select(Notification).where(
                Notification.id == notification_id,
                Notification.recipient_user_id == user_id,
            )
        )
        if item is None:
            return None
        if item.read_at is None:
            item.read_at = datetime.now(UTC)
            await self.session.commit()
        return self._read(item)

    async def mark_all_read(self, user_id: UUID) -> int:
        result = await self.session.execute(
            update(Notification)
            .where(
                Notification.recipient_user_id == user_id,
                Notification.read_at.is_(None),
            )
            .values(read_at=datetime.now(UTC))
        )
        await self.session.commit()
        return result.rowcount  # type: ignore[attr-defined,no-any-return]

    async def update_subscription(
        self, user_id: UUID, payload: SubscriptionUpdate
    ) -> None:
        item = await self.session.scalar(
            select(NotificationSubscription).where(
                NotificationSubscription.user_id == user_id,
                NotificationSubscription.provider == payload.provider,
                NotificationSubscription.template_key == payload.template_key,
            )
        )
        if item is None:
            self.session.add(
                NotificationSubscription(
                    user_id=user_id,
                    provider=payload.provider,
                    template_key=payload.template_key,
                    status=payload.status,
                )
            )
        else:
            item.status = payload.status
        await self.session.commit()

    async def generate_next_day_reminders(self, now: datetime | None = None) -> int:
        current = now or datetime.now(UTC)
        local = current.astimezone(ZoneInfo("Asia/Shanghai"))
        start_local = (local + timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        end_local = start_local + timedelta(days=1)
        statement = (
            select(Appointment)
            .join(ClassSchedule)
            .where(
                Appointment.status == AppointmentStatus.RESERVED,
                ClassSchedule.starts_at >= start_local.astimezone(UTC),
                ClassSchedule.starts_at < end_local.astimezone(UTC),
            )
            .options(
                selectinload(Appointment.schedule).selectinload(ClassSchedule.teacher),
                selectinload(Appointment.user),
            )
        )
        appointments = list((await self.session.scalars(statement)).all())
        created = 0
        for appointment in appointments:
            event_key = f"appointment.next_day_reminder:{appointment.id}:student"
            if (
                await self.session.scalar(
                    select(Notification.id).where(Notification.event_key == event_key)
                )
                is not None
            ):
                continue
            self.add_appointment_notification(
                appointment=appointment,
                kind="appointment.next_day_reminder",
                recipient_type=NotificationRecipientType.USER,
                title="明天有预约课程",
                content="你预约的课程将于明天开始，请提前安排时间。",
                template_key="appointment_next_day_reminder",
            )
            created += 1
        await self.session.commit()
        return created

    @staticmethod
    def _read(item: Notification) -> NotificationRead:
        return NotificationRead(
            id=item.id,
            kind=item.kind,
            title=item.title,
            content=item.content,
            appointment_id=item.appointment_id,
            page_path=item.page_path,
            read_at=item.read_at,
            created_at=item.created_at,
        )
