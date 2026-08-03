from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_session
from app.schemas.auth import AdminLoginRequest, AdminTokenResponse
from app.services.auth_service import AuthService, InvalidCredentialsError

router = APIRouter(prefix="/auth", tags=["admin-auth"])


@router.post("/login", response_model=AdminTokenResponse)
async def login(
    payload: AdminLoginRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AdminTokenResponse:
    try:
        return await AuthService(session, get_settings()).login(
            payload.username,
            payload.password,
        )
    except InvalidCredentialsError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
        ) from error
