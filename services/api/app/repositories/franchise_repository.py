from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.franchise import FranchisePage


class FranchiseRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_store(self, store_id: UUID) -> FranchisePage | None:
        result = await self.session.execute(
            select(FranchisePage).where(FranchisePage.store_id == store_id)
        )
        return result.scalar_one_or_none()

    def add(self, page: FranchisePage) -> None:
        self.session.add(page)
