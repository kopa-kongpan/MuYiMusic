import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admin import AdminUser
from app.models.notification import TeacherAccount, TeacherBindCode
from app.models.schedule import Teacher
from app.models.user import User
from app.schemas.teacher_portal import (
    TeacherBindCodeRead,
    TeacherIdentityListResponse,
    TeacherIdentityRead,
)
from app.services.store_service import can_access_store


class TeacherPortalNotFoundError(Exception):
    pass


class TeacherPortalConflictError(Exception):
    pass


class TeacherPortalService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_bind_code(
        self,
        *,
        store_id: UUID,
        teacher_id: UUID,
        admin_user: AdminUser,
    ) -> TeacherBindCodeRead:
        teacher = await self.session.get(Teacher, teacher_id)
        if (
            teacher is None
            or teacher.store_id != store_id
            or not can_access_store(admin_user, store_id)
        ):
            raise TeacherPortalNotFoundError
        now = datetime.now(UTC)
        code = secrets.token_urlsafe(9).replace("-", "").replace("_", "")[:12]
        self.session.add(
            TeacherBindCode(
                teacher_id=teacher_id,
                code_hash=self._hash(code),
                created_by_admin_id=admin_user.id,
                expires_at=now + timedelta(minutes=15),
            )
        )
        await self.session.commit()
        return TeacherBindCodeRead(code=code, expires_at=now + timedelta(minutes=15))

    async def bind(
        self, *, user: User, code: str, provider: str
    ) -> TeacherIdentityRead:
        now = datetime.now(UTC)
        bind_code = await self.session.scalar(
            select(TeacherBindCode)
            .where(TeacherBindCode.code_hash == self._hash(code))
            .with_for_update()
        )
        if bind_code is None:
            raise TeacherPortalNotFoundError
        if bind_code.used_at is not None or bind_code.expires_at <= now:
            raise TeacherPortalConflictError("绑定码已使用或已过期")
        teacher = await self.session.get(Teacher, bind_code.teacher_id)
        if teacher is None or not teacher.is_active:
            raise TeacherPortalConflictError("教师资料不可用")
        existing = await self.session.scalar(
            select(TeacherAccount).where(
                TeacherAccount.teacher_id == teacher.id,
                TeacherAccount.provider == provider,
            )
        )
        if existing is not None:
            raise TeacherPortalConflictError("该教师已绑定账号")
        bind_code.used_by_user_id = user.id
        bind_code.used_at = now
        self.session.add(
            TeacherAccount(teacher_id=teacher.id, user_id=user.id, provider=provider)
        )
        try:
            await self.session.commit()
        except IntegrityError as error:
            await self.session.rollback()
            raise TeacherPortalConflictError("教师账号绑定冲突") from error
        return self._identity(teacher, provider)

    async def identities(self, user_id: UUID) -> TeacherIdentityListResponse:
        rows = (
            await self.session.execute(
                select(TeacherAccount, Teacher)
                .join(Teacher, Teacher.id == TeacherAccount.teacher_id)
                .where(TeacherAccount.user_id == user_id, Teacher.is_active.is_(True))
                .order_by(Teacher.created_at, Teacher.id)
            )
        ).all()
        return TeacherIdentityListResponse(
            items=[
                self._identity(teacher, account.provider) for account, teacher in rows
            ]
        )

    async def require_teacher(self, user_id: UUID, teacher_id: UUID) -> Teacher:
        teacher = await self.session.scalar(
            select(Teacher)
            .join(TeacherAccount, TeacherAccount.teacher_id == Teacher.id)
            .where(
                Teacher.id == teacher_id,
                TeacherAccount.user_id == user_id,
                Teacher.is_active.is_(True),
            )
        )
        if teacher is None:
            raise TeacherPortalNotFoundError
        return teacher

    @staticmethod
    def _identity(teacher: Teacher, provider: str) -> TeacherIdentityRead:
        return TeacherIdentityRead(
            teacher_id=teacher.id,
            store_id=teacher.store_id,
            teacher_name=teacher.name,
            provider=provider,
        )

    @staticmethod
    def _hash(code: str) -> str:
        return hashlib.sha256(code.encode()).hexdigest()
