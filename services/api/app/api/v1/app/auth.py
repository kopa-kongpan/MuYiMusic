from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_session
from app.providers.miniapp_identity import (
    IdentityProviderNotConfiguredError,
    IdentityProviderUnavailableError,
    InvalidPlatformCodeError,
    MiniAppIdentityProvider,
    get_miniapp_identity_provider,
)
from app.schemas.user import UserLoginRequest, UserTokenResponse
from app.services.user_service import UserDisabledError, UserService

router = APIRouter(prefix="/auth", tags=["app-auth"])


@router.post("/login", response_model=UserTokenResponse)
async def login(
    payload: UserLoginRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    identity_provider: Annotated[
        MiniAppIdentityProvider,
        Depends(get_miniapp_identity_provider),
    ],
) -> UserTokenResponse:
    try:
        return await UserService(session, get_settings(), identity_provider).login(
            payload
        )
    except IdentityProviderNotConfiguredError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="当前登录平台尚未配置",
        ) from error
    except IdentityProviderUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="登录平台暂时不可用，请稍后重试",
        ) from error
    except InvalidPlatformCodeError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="平台登录凭证无效或已过期",
        ) from error
    except UserDisabledError as error:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="用户账号已停用",
        ) from error
