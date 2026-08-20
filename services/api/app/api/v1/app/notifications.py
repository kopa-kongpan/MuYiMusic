from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.core.database import get_session
from app.models.user import User
from app.schemas.notification import (
    NotificationListResponse,
    NotificationRead,
    NotificationUnreadResponse,
    SubscriptionUpdate,
)
from app.services.notification_service import NotificationService

router = APIRouter(prefix="/me/notifications", tags=["app-notifications"])
CurrentUser = Annotated[User, Depends(get_current_user)]
Session = Annotated[AsyncSession, Depends(get_session)]


@router.get("", response_model=NotificationListResponse)
async def list_notifications(
    current_user: CurrentUser,
    session: Session,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> NotificationListResponse:
    return await NotificationService(session).list_user(
        current_user.id, page, page_size
    )


@router.get("/unread", response_model=NotificationUnreadResponse)
async def unread_count(
    current_user: CurrentUser, session: Session
) -> NotificationUnreadResponse:
    result = await NotificationService(session).list_user(current_user.id, 1, 1)
    return NotificationUnreadResponse(unread_count=result.unread_count)


@router.post("/{notification_id}/read", response_model=NotificationRead)
async def mark_read(
    notification_id: UUID, current_user: CurrentUser, session: Session
) -> NotificationRead:
    item = await NotificationService(session).mark_read(
        current_user.id, notification_id
    )
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="消息不存在")
    return item


@router.post("/read-all", status_code=status.HTTP_204_NO_CONTENT)
async def mark_all_read(current_user: CurrentUser, session: Session) -> Response:
    await NotificationService(session).mark_all_read(current_user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put("/subscription", status_code=status.HTTP_204_NO_CONTENT)
async def update_subscription(
    payload: SubscriptionUpdate, current_user: CurrentUser, session: Session
) -> Response:
    await NotificationService(session).update_subscription(current_user.id, payload)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
