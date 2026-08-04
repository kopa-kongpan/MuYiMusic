from datetime import datetime
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.store_content import (
    ContentBlockStatus,
    ContentBlockType,
    StoreContentBlock,
)


class StoreContentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, content_id: UUID) -> StoreContentBlock | None:
        return await self.session.get(StoreContentBlock, content_id)

    async def list_admin(
        self,
        *,
        store_id: UUID,
        block_type: ContentBlockType | None,
        status: ContentBlockStatus | None,
        page: int,
        page_size: int,
    ) -> tuple[list[StoreContentBlock], int]:
        filters = [StoreContentBlock.store_id == store_id]
        if block_type is not None:
            filters.append(StoreContentBlock.block_type == block_type)
        if status is not None:
            filters.append(StoreContentBlock.status == status)
        count_statement = select(func.count(StoreContentBlock.id)).where(*filters)
        total = int(await self.session.scalar(count_statement) or 0)
        statement = (
            select(StoreContentBlock)
            .where(*filters)
            .order_by(
                StoreContentBlock.sort_order,
                StoreContentBlock.created_at,
                StoreContentBlock.id,
            )
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        items = list((await self.session.scalars(statement)).all())
        return items, total

    async def list_public(
        self,
        *,
        store_id: UUID,
        now: datetime,
    ) -> list[StoreContentBlock]:
        statement = (
            select(StoreContentBlock)
            .where(
                StoreContentBlock.store_id == store_id,
                StoreContentBlock.status == ContentBlockStatus.ENABLED,
                or_(
                    StoreContentBlock.starts_at.is_(None),
                    StoreContentBlock.starts_at <= now,
                ),
                or_(
                    StoreContentBlock.ends_at.is_(None),
                    StoreContentBlock.ends_at > now,
                ),
            )
            .order_by(
                StoreContentBlock.sort_order,
                StoreContentBlock.created_at,
                StoreContentBlock.id,
            )
        )
        return list((await self.session.scalars(statement)).all())

    async def list_by_ids(self, ids: set[UUID]) -> list[StoreContentBlock]:
        if not ids:
            return []
        statement = select(StoreContentBlock).where(StoreContentBlock.id.in_(ids))
        return list((await self.session.scalars(statement)).all())

    def add(self, content: StoreContentBlock) -> None:
        self.session.add(content)
