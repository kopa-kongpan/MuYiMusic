from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admin import AdminUser
from app.models.franchise import FranchisePage
from app.models.store import StoreStatus
from app.repositories.audit_repository import AuditRepository
from app.repositories.franchise_repository import FranchiseRepository
from app.repositories.store_repository import StoreRepository
from app.schemas.franchise import (
    FranchisePagePublicRead,
    FranchisePageRead,
    FranchisePageUpdate,
)
from app.services.store_service import can_access_store


class FranchisePageNotFoundError(Exception):
    pass


def franchise_snapshot(page: FranchisePage) -> dict[str, Any]:
    return FranchisePageUpdate.model_validate(page, from_attributes=True).model_dump()


class FranchiseService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = FranchiseRepository(session)
        self.store_repository = StoreRepository(session)
        self.audit_repository = AuditRepository(session)

    async def get_admin(
        self, store_id: UUID, admin_user: AdminUser
    ) -> FranchisePageRead | None:
        await self._require_store_access(store_id, admin_user)
        page = await self.repository.get_by_store(store_id)
        return FranchisePageRead.model_validate(page) if page else None

    async def upsert(
        self, store_id: UUID, payload: FranchisePageUpdate, admin_user: AdminUser
    ) -> FranchisePageRead:
        await self._require_store_access(store_id, admin_user)
        page = await self.repository.get_by_store(store_id)
        before = franchise_snapshot(page) if page else None
        if page is None:
            page = FranchisePage(store_id=store_id, **payload.model_dump())
            self.repository.add(page)
            action = "franchise_page.create"
        else:
            for field, value in payload.model_dump().items():
                setattr(page, field, value)
            action = "franchise_page.update"
        try:
            await self.session.flush()
            self.audit_repository.add(
                admin_user_id=admin_user.id,
                action=action,
                resource_type="franchise_page",
                resource_id=str(page.id),
                details={"before": before, "after": franchise_snapshot(page)},
            )
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise
        await self.session.refresh(page)
        return FranchisePageRead.model_validate(page)

    async def get_public(self, store_id: UUID) -> FranchisePagePublicRead:
        store = await self.store_repository.get(store_id)
        if store is None or store.status != StoreStatus.ACTIVE:
            raise FranchisePageNotFoundError
        page = await self.repository.get_by_store(store_id)
        if page is None:
            return FranchisePagePublicRead(
                title="携手木易音乐，共创音乐教育新未来",
                introduction=(
                    "我们期待与认同音乐教育价值的伙伴共同成长，"
                    "把专业、温暖的音乐学习体验带给更多家庭。"
                ),
                advantages="成熟的课程体系\n专业的师资培养\n持续的品牌运营支持",
                support_policy="选址与筹备支持\n课程及教学支持\n运营与市场推广支持",
                application_process="提交合作意向\n合作顾问沟通\n项目评估\n签约与开店筹备",
                contact_name=f"{store.name}合作顾问",
                contact_phone=store.phone,
                contact_wechat=None,
            )
        if not page.is_published:
            raise FranchisePageNotFoundError
        return FranchisePagePublicRead.model_validate(page, from_attributes=True)

    async def _require_store_access(
        self, store_id: UUID, admin_user: AdminUser
    ) -> None:
        if not can_access_store(admin_user, store_id):
            raise FranchisePageNotFoundError
        if await self.store_repository.get(store_id) is None:
            raise FranchisePageNotFoundError
