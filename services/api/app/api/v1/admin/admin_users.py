from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import require_platform_admin
from app.core.database import get_session
from app.models.admin import AdminUser
from app.schemas.admin_user import (
    AdminUserCreate,
    AdminUserListResponse,
    AdminUserOptionsResponse,
    AdminUserPasswordReset,
    AdminUserRead,
    AdminUserUpdate,
)
from app.services.admin_user_service import (
    AdminUserNotFoundError,
    AdminUserService,
    CannotDisableCurrentAdminError,
    DuplicateAdminUsernameError,
    InvalidAdminUserError,
    ProtectedAdminUserError,
)

router = APIRouter(prefix="/admin-users", tags=["admin-users"])
AdminManager = Annotated[
    AdminUser,
    Depends(require_platform_admin()),
]


@router.get("", response_model=AdminUserListResponse)
async def list_admin_users(
    session: Annotated[AsyncSession, Depends(get_session)],
    _current_admin: AdminManager,
    keyword: Annotated[str | None, Query(max_length=64)] = None,
    is_active: bool | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> AdminUserListResponse:
    return await AdminUserService(session).list_users(
        keyword=keyword,
        is_active=is_active,
        page=page,
        page_size=page_size,
    )


@router.get("/options", response_model=AdminUserOptionsResponse)
async def admin_user_options(
    session: Annotated[AsyncSession, Depends(get_session)],
    _current_admin: AdminManager,
) -> AdminUserOptionsResponse:
    return await AdminUserService(session).options()


@router.post("", response_model=AdminUserRead, status_code=status.HTTP_201_CREATED)
async def create_admin_user(
    payload: AdminUserCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
    current_admin: AdminManager,
) -> AdminUserRead:
    try:
        return await AdminUserService(session).create(
            payload=payload,
            operator=current_admin,
        )
    except DuplicateAdminUsernameError as error:
        raise HTTPException(status_code=409, detail="账号用户名已存在") from error
    except InvalidAdminUserError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.patch("/{admin_user_id}", response_model=AdminUserRead)
async def update_admin_user(
    admin_user_id: UUID,
    payload: AdminUserUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
    current_admin: AdminManager,
) -> AdminUserRead:
    try:
        return await AdminUserService(session).update(
            admin_user_id=admin_user_id,
            payload=payload,
            operator=current_admin,
        )
    except AdminUserNotFoundError as error:
        raise HTTPException(status_code=404, detail="运营账号不存在") from error
    except ProtectedAdminUserError as error:
        raise HTTPException(
            status_code=422,
            detail="平台管理员账号不能通过此处管理",
        ) from error
    except CannotDisableCurrentAdminError as error:
        raise HTTPException(status_code=409, detail="当前登录账号不能停用") from error
    except InvalidAdminUserError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.post("/{admin_user_id}/reset-password", response_model=AdminUserRead)
async def reset_admin_user_password(
    admin_user_id: UUID,
    payload: AdminUserPasswordReset,
    session: Annotated[AsyncSession, Depends(get_session)],
    current_admin: AdminManager,
) -> AdminUserRead:
    try:
        return await AdminUserService(session).reset_password(
            admin_user_id=admin_user_id,
            payload=payload,
            operator=current_admin,
        )
    except AdminUserNotFoundError as error:
        raise HTTPException(status_code=404, detail="运营账号不存在") from error
    except ProtectedAdminUserError as error:
        raise HTTPException(
            status_code=422,
            detail="平台管理员账号不能通过此处管理",
        ) from error
