from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog


class AuditRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def add(
        self,
        *,
        admin_user_id: UUID,
        action: str,
        resource_type: str,
        resource_id: str,
        details: dict[str, Any],
    ) -> AuditLog:
        audit_log = AuditLog(
            admin_user_id=admin_user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
        )
        self.session.add(audit_log)
        return audit_log
