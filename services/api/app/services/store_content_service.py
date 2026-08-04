from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admin import AdminUser
from app.models.store import Store, StoreStatus
from app.models.store_content import (
    ContentBlockStatus,
    ContentBlockType,
    ContentJumpType,
    StoreContentBlock,
)
from app.providers.object_storage import ObjectStorageProvider
from app.repositories.audit_repository import AuditRepository
from app.repositories.store_content_repository import StoreContentRepository
from app.repositories.store_repository import StoreRepository
from app.schemas.store import StorePublicRead
from app.schemas.store_content import (
    ContentBlockAdminListResponse,
    ContentBlockCreate,
    ContentBlockPublicRead,
    ContentBlockRead,
    ContentBlockUpdate,
    ContentOrderUpdate,
    StoreHomeResponse,
    validate_display_window,
    validate_jump_target,
)
from app.services.store_service import can_access_store


class ContentBlockNotFoundError(Exception):
    pass


class InvalidContentBlockError(Exception):
    pass


class InvalidContentOrderError(Exception):
    pass


class PublicStoreNotFoundError(Exception):
    pass


def content_snapshot(content: StoreContentBlock) -> dict[str, Any]:
    return {
        "store_id": str(content.store_id),
        "block_type": content.block_type.value,
        "title": content.title,
        "media_object_key": content.media_object_key,
        "jump_type": content.jump_type.value,
        "jump_target": content.jump_target,
        "sort_order": content.sort_order,
        "status": content.status.value,
        "starts_at": content.starts_at.isoformat() if content.starts_at else None,
        "ends_at": content.ends_at.isoformat() if content.ends_at else None,
    }


class StoreContentService:
    def __init__(
        self,
        session: AsyncSession,
        storage: ObjectStorageProvider,
    ) -> None:
        self.session = session
        self.storage = storage
        self.repository = StoreContentRepository(session)
        self.store_repository = StoreRepository(session)
        self.audit_repository = AuditRepository(session)

    async def list_admin(
        self,
        *,
        store_id: UUID,
        admin_user: AdminUser,
        block_type: ContentBlockType | None,
        status: ContentBlockStatus | None,
        page: int,
        page_size: int,
    ) -> ContentBlockAdminListResponse:
        await self._require_store_access(store_id, admin_user)
        items, total = await self.repository.list_admin(
            store_id=store_id,
            block_type=block_type,
            status=status,
            page=page,
            page_size=page_size,
        )
        return ContentBlockAdminListResponse(
            items=[self._to_read(item) for item in items],
            total=total,
            page=page,
            page_size=page_size,
        )

    async def get_public_home(self, store_id: UUID) -> StoreHomeResponse:
        store = await self.store_repository.get(store_id)
        if store is None or store.status != StoreStatus.ACTIVE:
            raise PublicStoreNotFoundError
        items = await self.repository.list_public(
            store_id=store_id,
            now=datetime.now(UTC),
        )
        return StoreHomeResponse(
            store=StorePublicRead.model_validate(store),
            content_blocks=[self._to_public_read(item) for item in items],
        )

    async def create(
        self,
        *,
        store_id: UUID,
        payload: ContentBlockCreate,
        admin_user: AdminUser,
    ) -> ContentBlockRead:
        await self._require_store_access(store_id, admin_user)
        self._validate_values(store_id=store_id, **payload.model_dump())
        content = StoreContentBlock(store_id=store_id, **payload.model_dump())
        try:
            self.repository.add(content)
            await self.session.flush()
            self.audit_repository.add(
                admin_user_id=admin_user.id,
                action="store_content.create",
                resource_type="store_content",
                resource_id=str(content.id),
                details={"after": content_snapshot(content)},
            )
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise
        await self.session.refresh(content)
        return self._to_read(content)

    async def update(
        self,
        *,
        store_id: UUID,
        content_id: UUID,
        payload: ContentBlockUpdate,
        admin_user: AdminUser,
    ) -> ContentBlockRead:
        await self._require_store_access(store_id, admin_user)
        content = await self.repository.get(content_id)
        if content is None or content.store_id != store_id:
            raise ContentBlockNotFoundError
        changes = payload.model_dump(exclude_unset=True)
        if not changes:
            return self._to_read(content)
        required_fields = {
            "block_type",
            "title",
            "jump_type",
            "sort_order",
            "status",
        }
        if any(
            field in changes and changes[field] is None for field in required_fields
        ):
            raise InvalidContentBlockError("必填内容字段不能设置为空")
        values = content_snapshot(content)
        values.update(changes)
        self._validate_values(
            store_id=store_id,
            block_type=ContentBlockType(values["block_type"]),
            title=str(values["title"]),
            media_object_key=values["media_object_key"],
            jump_type=ContentJumpType(values["jump_type"]),
            jump_target=values["jump_target"],
            sort_order=int(values["sort_order"]),
            status=ContentBlockStatus(values["status"]),
            starts_at=changes.get("starts_at", content.starts_at),
            ends_at=changes.get("ends_at", content.ends_at),
        )
        before = content_snapshot(content)
        for field, value in changes.items():
            setattr(content, field, value)
        try:
            await self.session.flush()
            self.audit_repository.add(
                admin_user_id=admin_user.id,
                action="store_content.update",
                resource_type="store_content",
                resource_id=str(content.id),
                details={"before": before, "after": content_snapshot(content)},
            )
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise
        await self.session.refresh(content)
        return self._to_read(content)

    async def reorder(
        self,
        *,
        store_id: UUID,
        payload: ContentOrderUpdate,
        admin_user: AdminUser,
    ) -> list[ContentBlockRead]:
        await self._require_store_access(store_id, admin_user)
        requested = {item.id: item.sort_order for item in payload.items}
        contents = await self.repository.list_by_ids(set(requested))
        if len(contents) != len(requested) or any(
            content.store_id != store_id for content in contents
        ):
            raise InvalidContentOrderError
        before = {str(content.id): content.sort_order for content in contents}
        for content in contents:
            content.sort_order = requested[content.id]
        try:
            await self.session.flush()
            self.audit_repository.add(
                admin_user_id=admin_user.id,
                action="store_content.reorder",
                resource_type="store",
                resource_id=str(store_id),
                details={
                    "before": before,
                    "after": {str(item.id): item.sort_order for item in contents},
                },
            )
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise
        items, _ = await self.repository.list_admin(
            store_id=store_id,
            block_type=None,
            status=None,
            page=1,
            page_size=100,
        )
        return [self._to_read(item) for item in items]

    async def _require_store_access(
        self,
        store_id: UUID,
        admin_user: AdminUser,
    ) -> Store:
        if not can_access_store(admin_user, store_id):
            raise ContentBlockNotFoundError
        store = await self.store_repository.get(store_id)
        if store is None:
            raise ContentBlockNotFoundError
        return store

    def _validate_values(
        self,
        *,
        store_id: UUID,
        block_type: ContentBlockType,
        title: str,
        media_object_key: str | None,
        jump_type: ContentJumpType,
        jump_target: str | None,
        sort_order: int,
        status: ContentBlockStatus,
        starts_at: datetime | None,
        ends_at: datetime | None,
    ) -> None:
        del title, sort_order, status
        if block_type != ContentBlockType.SHORTCUT and not media_object_key:
            raise InvalidContentBlockError("图片或视频内容必须设置媒体对象")
        if media_object_key and not self.storage.is_home_object_key(
            store_id,
            media_object_key,
        ):
            raise InvalidContentBlockError("媒体对象不属于当前门店")
        if (
            block_type == ContentBlockType.SHORTCUT
            and jump_type == ContentJumpType.NONE
        ):
            raise InvalidContentBlockError("快捷入口必须设置跳转目标")
        try:
            validate_jump_target(jump_type, jump_target)
            validate_display_window(starts_at, ends_at)
        except ValueError as error:
            raise InvalidContentBlockError(str(error)) from error

    def _to_read(self, content: StoreContentBlock) -> ContentBlockRead:
        result = ContentBlockRead.model_validate(content)
        result.media_url = self.storage.media_url(content.media_object_key)
        return result

    def _to_public_read(
        self,
        content: StoreContentBlock,
    ) -> ContentBlockPublicRead:
        return ContentBlockPublicRead(
            id=content.id,
            block_type=content.block_type,
            title=content.title,
            media_url=self.storage.media_url(content.media_object_key),
            jump_type=content.jump_type,
            jump_target=content.jump_target,
            sort_order=content.sort_order,
        )
