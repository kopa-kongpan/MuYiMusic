from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.admin import AdminUser, Role


class AdminRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_username(self, username: str) -> AdminUser | None:
        statement = (
            select(AdminUser)
            .where(AdminUser.username == username)
            .options(selectinload(AdminUser.roles).selectinload(Role.permissions))
        )
        return (await self.session.scalars(statement)).one_or_none()

    async def get_by_id(self, admin_user_id: UUID) -> AdminUser | None:
        statement = (
            select(AdminUser)
            .where(AdminUser.id == admin_user_id)
            .options(selectinload(AdminUser.roles).selectinload(Role.permissions))
        )
        return (await self.session.scalars(statement)).one_or_none()
