from fastapi.concurrency import run_in_threadpool
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.security import create_access_token, verify_password
from app.models.admin import AdminUser
from app.repositories.admin_repository import AdminRepository
from app.schemas.auth import AdminProfile, AdminTokenResponse


class InvalidCredentialsError(Exception):
    pass


PLATFORM_ADMIN_ROLE_CODE = "platform_admin"


def permission_codes(admin_user: AdminUser) -> set[str]:
    return {
        permission.code for role in admin_user.roles for permission in role.permissions
    }


def has_platform_scope(admin_user: AdminUser) -> bool:
    return any(role.code == PLATFORM_ADMIN_ROLE_CODE for role in admin_user.roles)


class AuthService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.repository = AdminRepository(session)
        self.settings = settings

    async def login(self, username: str, password: str) -> AdminTokenResponse:
        admin_user = await self.repository.get_by_username(username)
        if admin_user is None or not admin_user.is_active:
            raise InvalidCredentialsError

        is_valid = await run_in_threadpool(
            verify_password,
            password,
            admin_user.password_hash,
        )
        if not is_valid:
            raise InvalidCredentialsError

        secret = self.settings.jwt_secret
        if secret is None:
            raise RuntimeError("JWT_SECRET is required")

        permissions = sorted(permission_codes(admin_user))
        expires_in = self.settings.jwt_access_token_minutes * 60
        return AdminTokenResponse(
            access_token=create_access_token(
                admin_user.id,
                secret,
                self.settings.jwt_access_token_minutes,
                subject_type="admin",
            ),
            expires_in=expires_in,
            admin=AdminProfile(
                id=admin_user.id,
                username=admin_user.username,
                permissions=permissions,
            ),
        )
