from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.payment import PaymentStatus
from app.models.wechat_fulfillment import FulfillmentStatus
from app.schemas.user import OrderRead


class FulfillmentConfirmRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    logistics_type: Literal[3, 4]
    item_description: str = Field(min_length=1, max_length=120)
    evidence: str = Field(min_length=1, max_length=500)


class FulfillmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    payment_id: UUID
    status: FulfillmentStatus
    logistics_type: Literal[3, 4]
    item_description: str
    evidence: str
    attempts: int
    last_error: str | None
    confirmed_at: datetime
    next_attempt_at: datetime | None
    sent_at: datetime | None


class AdminOrderRead(OrderRead):
    wechat_payment_status: PaymentStatus | None = None
    fulfillment: FulfillmentRead | None = None


class AdminOrderListResponse(BaseModel):
    items: list[AdminOrderRead]
    total: int
    page: int
    page_size: int
