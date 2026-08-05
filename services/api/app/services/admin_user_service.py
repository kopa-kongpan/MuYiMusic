from typing import Any
from uuid import UUID

from fastapi.concurrency import run_in_threadpool
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.admin import AdminUser, Role
from app.repositories.admin_repository import AdminRepository
from app.repositories.audit_repository import AuditRepository
from app.schemas.admin_user import (
    AdminRoleRead,
    AdminStoreOption,
    AdminUserCreate,
    AdminUserListResponse,
    AdminUserOptionsResponse,
    AdminUserPasswordReset,
    AdminUserRead,
    AdminUserUpdate,
)


class AdminUserNotFoundError(Exception):
    pass


class InvalidAdminUserError(Exception):
    pass


class DuplicateAdminUsernameError(Exception):
    pass


class CannotDisableCurrentAdminError(Exception):
    pass


class ProtectedAdminUserError(Exception):
    pass


def _role_read(role: Role) -> AdminRoleRead:
    return AdminRoleRead(
        code=role.code,
        name=role.name,
        permissions=sorted(permission.code for permission in role.permissions),
    )


def _store_option(store: Any) -> AdminStoreOption:
    return AdminStoreOption(
        id=store.id,
        name=store.name,
        city=store.city,
        status=store.status.value,
    )


def _user_snapshot(admin_user: AdminUser) -> dict[str, Any]:
    return {
        "username": admin_user.username,
        "is_active": admin_user.is_active,
        "roles": [role.code for role in admin_user.roles],
        "store_ids": [str(store.id) for store in admin_user.stores],
    }


def _user_read(admin_user: AdminUser) -> AdminUserRead:
    return AdminUserRead(
        id=admin_user.id,
        username=admin_user.username,
        is_active=admin_user.is_active,
        roles=[_role_read(role) for role in admin_user.roles],
        stores=[_store_option(store) for store in admin_user.stores],
        created_at=admin_user.created_at,
        updated_at=admin_user.updated_at,
    )


class AdminUserService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = AdminRepository(session)
        self.audit_repository = AuditRepository(session)

    async def list_users(
        self,
        *,
        keyword: str | None,
        is_active: bool | None,
        page: int,
        page_size: int,
    ) -> AdminUserListResponse:
        users, total = await self.repository.list_managed_users(
            keyword=keyword,
            is_active=is_active,
            page=page,
            page_size=page_size,
        )
        return AdminUserListResponse(
            items=[_user_read(user) for user in users],
            total=total,
            page=page,
            page_size=page_size,
        )

    async def options(self) -> AdminUserOptionsResponse:
        roles = await self.repository.list_managed_roles()
        stores = await self.repository.list_stores()
        return AdminUserOptionsResponse(
            roles=[_role_read(role) for role in roles],
            stores=[_store_option(store) for store in stores],
        )

    async def _role_and_stores(
        self,
        *,
        role_code: str,
        store_ids: list[UUID],
    ) -> tuple[Role, list[Any]]:
        if role_code == "platform_admin":
            raise InvalidAdminUserError("运营账号不能使用平台管理员角色")
        role = await self.repository.get_role(role_code)
        if role is None:
            raise InvalidAdminUserError("运营角色不存在")
        stores = await self.repository.get_stores(set(store_ids))
        if len(stores) != len(set(store_ids)):
            raise InvalidAdminUserError("存在不可用的门店授权")
        if not stores:
            raise InvalidAdminUserError("运营账号至少需要绑定一个门店")
        return role, stores

    async def _require_managed_user(self, admin_user_id: UUID) -> AdminUser:
        admin_user = await self.repository.get_by_id(admin_user_id)
        if admin_user is None:
            raise AdminUserNotFoundError
        if any(role.code == "platform_admin" for role in admin_user.roles):
            raise ProtectedAdminUserError
        return admin_user

    async def create(
        self,
        *,
        payload: AdminUserCreate,
        operator: AdminUser,
    ) -> AdminUserRead:
        if await self.repository.get_by_username(payload.username) is not None:
            raise DuplicateAdminUsernameError
        role, stores = await self._role_and_stores(
            role_code=payload.role_code,
            store_ids=payload.store_ids,
        )
        admin_user = AdminUser(
            username=payload.username,
            password_hash=await run_in_threadpool(hash_password, payload.password),
            roles=[role],
            stores=stores,
        )
        try:
            self.repository.add(admin_user)
            await self.session.flush()
            self.audit_repository.add(
                admin_user_id=operator.id,
                action="admin_user.create",
                resource_type="admin_user",
                resource_id=str(admin_user.id),
                details={"after": _user_snapshot(admin_user)},
            )
            await self.session.commit()
        except IntegrityError as error:
            await self.session.rollback()
            raise DuplicateAdminUsernameError from error
        except Exception:
            await self.session.rollback()
            raise
        saved = await self.repository.get_by_id(admin_user.id)
        assert saved is not None
        return _user_read(saved)

    async def update(
        self,
        *,
        admin_user_id: UUID,
        payload: AdminUserUpdate,
        operator: AdminUser,
    ) -> AdminUserRead:
        target = await self._require_managed_user(admin_user_id)
        changes = payload.model_dump(exclude_unset=True, exclude_none=True)
        if changes.get("is_active") is False and target.id == operator.id:
            raise CannotDisableCurrentAdminError
        if not changes:
            return _user_read(target)
        before = _user_snapshot(target)
        if "role_code" in changes or "store_ids" in changes:
            role_code = str(changes.get("role_code", target.roles[0].code))
            store_ids = changes.get(
                "store_ids",
                [store.id for store in target.stores],
            )
            role, stores = await self._role_and_stores(
                role_code=role_code,
                store_ids=store_ids,
            )
            target.roles = [role]
            target.stores = stores
        if "is_active" in changes:
            target.is_active = bool(changes["is_active"])
        try:
            await self.session.flush()
            self.audit_repository.add(
                admin_user_id=operator.id,
                action="admin_user.update",
                resource_type="admin_user",
                resource_id=str(target.id),
                details={"before": before, "after": _user_snapshot(target)},
            )
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise
        saved = await self.repository.get_by_id(target.id)
        assert saved is not None
        return _user_read(saved)

    async def reset_password(
        self,
        *,
        admin_user_id: UUID,
        payload: AdminUserPasswordReset,
        operator: AdminUser,
    ) -> AdminUserRead:
        target = await self._require_managed_user(admin_user_id)
        target.password_hash = await run_in_threadpool(hash_password, payload.password)
        try:
            await self.session.flush()
            self.audit_repository.add(
                admin_user_id=operator.id,
                action="admin_user.password.reset",
                resource_type="admin_user",
                resource_id=str(target.id),
                details={"username": target.username},
            )
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise
        saved = await self.repository.get_by_id(target.id)
        assert saved is not None
        return _user_read(saved)
