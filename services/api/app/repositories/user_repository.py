from uuid import UUID

from sqlalchemy import exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.store import Store
from app.models.user import (
    CourseEntitlement,
    EntitlementStatus,
    IdentityProvider,
    Order,
    OrderStatus,
    ProviderAccount,
    User,
)


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_user(self, user_id: UUID) -> User | None:
        statement = (
            select(User)
            .where(User.id == user_id)
            .options(selectinload(User.provider_accounts))
        )
        return (await self.session.scalars(statement)).one_or_none()

    async def get_account(
        self,
        provider: IdentityProvider,
        provider_subject: str,
    ) -> ProviderAccount | None:
        statement = (
            select(ProviderAccount)
            .where(
                ProviderAccount.provider == provider,
                ProviderAccount.provider_subject == provider_subject,
            )
            .options(selectinload(ProviderAccount.user))
        )
        return (await self.session.scalars(statement)).one_or_none()

    def add_user(self, user: User) -> None:
        self.session.add(user)

    async def list_orders(
        self,
        *,
        user_id: UUID,
        store_id: UUID | None,
        status: OrderStatus | None,
        page: int,
        page_size: int,
    ) -> tuple[list[tuple[Order, str]], int]:
        filters = [Order.user_id == user_id]
        if store_id is not None:
            filters.append(Order.store_id == store_id)
        if status is not None:
            filters.append(Order.status == status)
        total = int(
            await self.session.scalar(select(func.count(Order.id)).where(*filters))
            or 0
        )
        statement = (
            select(Order, Store.name)
            .join(Store, Store.id == Order.store_id)
            .options(selectinload(Order.items))
            .where(*filters)
            .order_by(Order.created_at.desc(), Order.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = list((await self.session.execute(statement)).tuples().all())
        return rows, total

    async def list_entitlements(
        self,
        *,
        user_id: UUID,
        store_id: UUID | None,
        status: EntitlementStatus | None,
        page: int,
        page_size: int,
    ) -> tuple[list[tuple[CourseEntitlement, str]], int]:
        filters = [CourseEntitlement.user_id == user_id]
        if store_id is not None:
            filters.append(CourseEntitlement.store_id == store_id)
        if status is not None:
            filters.append(CourseEntitlement.status == status)
        total = int(
            await self.session.scalar(
                select(func.count(CourseEntitlement.id)).where(*filters)
            )
            or 0
        )
        statement = (
            select(CourseEntitlement, Store.name)
            .join(Store, Store.id == CourseEntitlement.store_id)
            .where(*filters)
            .order_by(CourseEntitlement.created_at.desc(), CourseEntitlement.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = list((await self.session.execute(statement)).tuples().all())
        return rows, total

    async def list_users_for_store(
        self,
        *,
        store_id: UUID,
        keyword: str | None,
        page: int,
        page_size: int,
    ) -> tuple[list[User], int]:
        store_relation = or_(
            exists().where(
                Order.user_id == User.id,
                Order.store_id == store_id,
            ),
            exists().where(
                CourseEntitlement.user_id == User.id,
                CourseEntitlement.store_id == store_id,
            ),
        )
        filters = [store_relation]
        if keyword:
            pattern = f"%{keyword}%"
            filters.append(
                or_(User.nickname.ilike(pattern), User.phone.ilike(pattern))
            )
        total = int(
            await self.session.scalar(select(func.count(User.id)).where(*filters))
            or 0
        )
        statement = (
            select(User)
            .options(selectinload(User.provider_accounts))
            .where(*filters)
            .order_by(User.created_at.desc(), User.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list((await self.session.scalars(statement)).all()), total

    async def user_store_counts(
        self,
        user_ids: list[UUID],
        store_id: UUID,
    ) -> tuple[dict[UUID, int], dict[UUID, int]]:
        if not user_ids:
            return {}, {}
        order_rows = await self.session.execute(
            select(Order.user_id, func.count(Order.id))
            .where(Order.user_id.in_(user_ids), Order.store_id == store_id)
            .group_by(Order.user_id)
        )
        entitlement_rows = await self.session.execute(
            select(CourseEntitlement.user_id, func.count(CourseEntitlement.id))
            .where(
                CourseEntitlement.user_id.in_(user_ids),
                CourseEntitlement.store_id == store_id,
            )
            .group_by(CourseEntitlement.user_id)
        )
        return (
            {user_id: int(count) for user_id, count in order_rows.tuples()},
            {user_id: int(count) for user_id, count in entitlement_rows.tuples()},
        )
