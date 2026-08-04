from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.models.store import Store, StoreStatus


class StoreRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, store_id: UUID) -> Store | None:
        return await self.session.get(Store, store_id)

    async def list_admin(
        self,
        *,
        keyword: str | None,
        status: StoreStatus | None,
        page: int,
        page_size: int,
        allowed_store_ids: set[UUID] | None,
    ) -> tuple[list[Store], int]:
        filters: list[ColumnElement[bool]] = []
        if allowed_store_ids is not None:
            filters.append(Store.id.in_(allowed_store_ids))
        if keyword:
            pattern = f"%{keyword}%"
            filters.append(
                or_(
                    Store.name.ilike(pattern),
                    Store.city.ilike(pattern),
                    Store.district.ilike(pattern),
                    Store.address.ilike(pattern),
                )
            )
        if status is not None:
            filters.append(Store.status == status)

        count_statement = select(func.count(Store.id)).where(*filters)
        total = int(await self.session.scalar(count_statement) or 0)
        statement = (
            select(Store)
            .where(*filters)
            .order_by(Store.sort_order, Store.created_at, Store.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        stores = list((await self.session.scalars(statement)).all())
        return stores, total

    async def list_public(self, keyword: str | None) -> list[Store]:
        filters = [Store.status == StoreStatus.ACTIVE]
        if keyword:
            pattern = f"%{keyword}%"
            filters.append(
                or_(
                    Store.name.ilike(pattern),
                    Store.city.ilike(pattern),
                    Store.district.ilike(pattern),
                    Store.address.ilike(pattern),
                )
            )
        statement = (
            select(Store)
            .where(*filters)
            .order_by(Store.sort_order, Store.created_at, Store.id)
        )
        return list((await self.session.scalars(statement)).all())

    def add(self, store: Store) -> None:
        self.session.add(store)
