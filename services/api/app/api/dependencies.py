from collections.abc import Awaitable, Callable
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_session
from app.core.security import decode_access_token
from app.models.admin import AdminUser
from app.repositories.admin_repository import AdminRepository
from app.services.auth_service import permission_codes

bearer_scheme = HTTPBearer(auto_error=False)
SessionDependency = Annotated[AsyncSession, Depends(get_session)]


async def get_current_admin(
    session: SessionDependency,
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ],
) -> AdminUser:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="请先登录",
        )
    secret = get_settings().jwt_secret
    if secret is None:
        raise RuntimeError("JWT_SECRET is required")
    try:
        admin_user_id = decode_access_token(credentials.credentials, secret)
    except jwt.InvalidTokenError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="登录状态已失效",
        ) from error
    admin_user = await AdminRepository(session).get_by_id(admin_user_id)
    if admin_user is None or not admin_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="管理员账号不可用",
        )
    return admin_user


def require_permission(
    permission_code: str,
) -> Callable[[AdminUser], Awaitable[AdminUser]]:
    async def dependency(
        current_admin: Annotated[AdminUser, Depends(get_current_admin)],
    ) -> AdminUser:
        if permission_code not in permission_codes(current_admin):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="没有执行此操作的权限",
            )
        return current_admin

    return dependency
