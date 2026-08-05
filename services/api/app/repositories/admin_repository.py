from typing import Any
from uuid import UUID

from sqlalchemy import func, not_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.admin import AdminUser, Role
from app.models.store import Store


class AdminRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def _admin_options(self) -> tuple[Any, Any]:
        role_options = selectinload(AdminUser.roles).selectinload(Role.permissions)
        return role_options, selectinload(AdminUser.stores)

    async def get_by_username(self, username: str) -> AdminUser | None:
        statement = (
            select(AdminUser)
            .where(AdminUser.username == username)
            .options(*self._admin_options())
        )
        return (await self.session.scalars(statement)).one_or_none()

    async def get_by_id(self, admin_user_id: UUID) -> AdminUser | None:
        statement = (
            select(AdminUser)
            .where(AdminUser.id == admin_user_id)
            .options(*self._admin_options())
        )
        return (await self.session.scalars(statement)).one_or_none()

    async def list_managed_users(
        self,
        *,
        keyword: str | None,
        is_active: bool | None,
        page: int,
        page_size: int,
    ) -> tuple[list[AdminUser], int]:
        filters = [
            not_(AdminUser.roles.any(Role.code == "platform_admin")),
        ]
        if keyword:
            filters.append(AdminUser.username.ilike(f"%{keyword}%"))
        if is_active is not None:
            filters.append(AdminUser.is_active == is_active)
        total = int(
            await self.session.scalar(select(func.count(AdminUser.id)).where(*filters))
            or 0
        )
        statement = (
            select(AdminUser)
            .where(*filters)
            .options(*self._admin_options())
            .order_by(AdminUser.created_at.desc(), AdminUser.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        users = list((await self.session.scalars(statement)).all())
        return users, total

    async def get_role(self, code: str) -> Role | None:
        statement = (
            select(Role)
            .where(Role.code == code)
            .options(selectinload(Role.permissions))
        )
        return (await self.session.scalars(statement)).one_or_none()

    async def list_managed_roles(self) -> list[Role]:
        statement = (
            select(Role)
            .where(Role.code != "platform_admin")
            .options(selectinload(Role.permissions))
            .order_by(Role.name, Role.code)
        )
        return list((await self.session.scalars(statement)).all())

    async def list_stores(self) -> list[Store]:
        statement = select(Store).order_by(Store.sort_order, Store.created_at, Store.id)
        return list((await self.session.scalars(statement)).all())

    async def get_stores(self, store_ids: set[UUID]) -> list[Store]:
        if not store_ids:
            return []
        statement = (
            select(Store)
            .where(Store.id.in_(store_ids))
            .order_by(Store.sort_order, Store.created_at, Store.id)
        )
        return list((await self.session.scalars(statement)).all())

    def add(self, admin_user: AdminUser) -> None:
        self.session.add(admin_user)
