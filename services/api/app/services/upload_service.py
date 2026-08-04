from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admin import AdminUser
from app.providers.object_storage import ObjectStorageProvider
from app.repositories.audit_repository import AuditRepository
from app.repositories.store_repository import StoreRepository
from app.schemas.store_content import UploadTicketRequest, UploadTicketResponse
from app.services.store_service import can_access_store


class UploadStoreNotFoundError(Exception):
    pass


class UploadService:
    def __init__(
        self,
        session: AsyncSession,
        storage: ObjectStorageProvider,
    ) -> None:
        self.session = session
        self.storage = storage
        self.store_repository = StoreRepository(session)
        self.audit_repository = AuditRepository(session)

    async def create_ticket(
        self,
        payload: UploadTicketRequest,
        admin_user: AdminUser,
    ) -> UploadTicketResponse:
        await self._require_store_access(payload.store_id, admin_user)
        ticket = self.storage.create_upload_ticket(
            store_id=payload.store_id,
            file_name=payload.file_name,
            content_type=payload.content_type,
            file_size=payload.file_size,
        )
        try:
            self.audit_repository.add(
                admin_user_id=admin_user.id,
                action="media.upload_ticket.create",
                resource_type="object",
                resource_id=ticket.object_key,
                details={
                    "store_id": str(payload.store_id),
                    "content_type": payload.content_type,
                    "file_size": payload.file_size,
                },
            )
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise
        return UploadTicketResponse(
            object_key=ticket.object_key,
            upload_url=ticket.upload_url,
            headers=ticket.headers,
            public_url=ticket.public_url,
            expires_at=ticket.expires_at,
            max_size_bytes=ticket.max_size_bytes,
        )

    async def _require_store_access(
        self,
        store_id: UUID,
        admin_user: AdminUser,
    ) -> None:
        if not can_access_store(admin_user, store_id):
            raise UploadStoreNotFoundError
        if await self.store_repository.get(store_id) is None:
            raise UploadStoreNotFoundError
