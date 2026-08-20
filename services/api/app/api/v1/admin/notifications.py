from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import require_permission
from app.core.config import get_settings
from app.core.database import get_session
from app.models.admin import AdminUser
from app.models.notification import NotificationDeliveryStatus
from app.schemas.notification import NotificationDeliveryListResponse
from app.services.notification_delivery_service import NotificationDeliveryService

router = APIRouter(prefix="/notifications", tags=["admin-notifications"])
NotificationManager = Annotated[
    AdminUser, Depends(require_permission("appointments:manage"))
]


def redis_client() -> Redis:
    return cast(
        Redis,
        Redis.from_url(get_settings().redis_url or "redis://redis:6379/0"),
    )


@router.get("/deliveries", response_model=NotificationDeliveryListResponse)
async def list_deliveries(
    session: Annotated[AsyncSession, Depends(get_session)],
    current_admin: NotificationManager,
    delivery_status: Annotated[
        NotificationDeliveryStatus | None, Query(alias="status")
    ] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> NotificationDeliveryListResponse:
    del current_admin
    redis = redis_client()
    try:
        return await NotificationDeliveryService(
            session, get_settings(), redis
        ).list_deliveries(status=delivery_status, page=page, page_size=page_size)
    finally:
        await redis.aclose()


@router.post("/deliveries/{delivery_id}/retry", status_code=status.HTTP_204_NO_CONTENT)
async def retry_delivery(
    delivery_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    current_admin: NotificationManager,
) -> None:
    del current_admin
    redis = redis_client()
    try:
        found = await NotificationDeliveryService(session, get_settings(), redis).retry(
            delivery_id
        )
    finally:
        await redis.aclose()
    if not found:
        raise HTTPException(status_code=404, detail="投递记录不存在")
