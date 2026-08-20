from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.notification import NotificationDeliveryStatus, SubscriptionStatus


class NotificationRead(BaseModel):
    id: UUID
    kind: str
    title: str
    content: str
    appointment_id: UUID | None
    page_path: str | None
    read_at: datetime | None
    created_at: datetime


class NotificationListResponse(BaseModel):
    items: list[NotificationRead]
    total: int
    unread_count: int
    page: int
    page_size: int


class NotificationUnreadResponse(BaseModel):
    unread_count: int


class SubscriptionUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    provider: str = Field(pattern="^(weapp|tt)$")
    template_key: str = Field(min_length=1, max_length=64)
    status: SubscriptionStatus


class NotificationDeliveryRead(BaseModel):
    id: UUID
    notification_id: UUID
    kind: str
    title: str
    channel: str
    template_key: str
    status: NotificationDeliveryStatus
    attempts: int
    last_error: str | None
    next_attempt_at: datetime | None
    sent_at: datetime | None
    created_at: datetime


class NotificationDeliveryListResponse(BaseModel):
    items: list[NotificationDeliveryRead]
    total: int
    page: int
    page_size: int
