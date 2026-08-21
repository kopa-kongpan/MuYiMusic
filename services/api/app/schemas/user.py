from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.product import ProductType
from app.models.user import (
    EntitlementStatus,
    IdentityProvider,
    OrderStatus,
    UserStatus,
)


class UserLoginRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    provider: IdentityProvider
    code: str = Field(min_length=8, max_length=512)
    nickname: str | None = Field(default=None, min_length=1, max_length=128)
    avatar_url: str | None = Field(default=None, max_length=1024)


class UserProfileUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    nickname: str | None = Field(default=None, min_length=1, max_length=128)
    avatar_url: str | None = Field(default=None, max_length=1024)


class UserProfile(BaseModel):
    id: UUID
    nickname: str
    avatar_url: str | None
    phone: str | None
    status: UserStatus


class UserTokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
    user: UserProfile


class OrderItemRead(BaseModel):
    id: UUID
    product_id: UUID | None
    product_sku_id: UUID | None
    product_name: str
    sku_name: str
    unit_price_cents: int
    quantity: int
    total_amount_cents: int
    lesson_count: int
    validity_days: int
    product_type: ProductType


class OrderRead(BaseModel):
    id: UUID
    order_no: str
    user_id: UUID
    store_id: UUID
    store_name: str
    status: OrderStatus
    total_amount_cents: int
    created_at: datetime
    updated_at: datetime
    items: list[OrderItemRead]


class OrderListResponse(BaseModel):
    items: list[OrderRead]
    total: int
    page: int
    page_size: int


class EntitlementVideoChapterRead(BaseModel):
    """已购权益下的视频章节：持有效权益时可获得播放地址。"""

    id: UUID
    title: str
    duration_seconds: int | None
    sort_order: int
    video_url: str | None


class CourseEntitlementRead(BaseModel):
    id: UUID
    user_id: UUID
    store_id: UUID
    store_name: str
    order_item_id: UUID | None
    product_id: UUID | None
    product_sku_id: UUID | None
    course_name: str
    product_type: ProductType
    total_lessons: int
    remaining_lessons: int
    reserved_lessons: int
    available_lessons: int
    valid_from: datetime
    expires_at: datetime | None
    status: EntitlementStatus
    created_at: datetime
    video_chapters: list[EntitlementVideoChapterRead] = Field(default_factory=list)


class CourseEntitlementListResponse(BaseModel):
    items: list[CourseEntitlementRead]
    total: int
    page: int
    page_size: int


class EntitlementGrantRequest(BaseModel):
    """管理员为已成交用户开通商品权益（线下成交后录入）。"""

    product_id: UUID
    sku_id: UUID
    quantity: int = Field(ge=1, le=99)
    idempotency_key: str = Field(min_length=8, max_length=128)


class EntitlementLessonUpdateRequest(BaseModel):
    """管理员修正课程权益的剩余课时。"""

    remaining_lessons: int = Field(ge=0, le=9999)
    reason: str = Field(min_length=1, max_length=500)


class UserAdminRead(BaseModel):
    id: UUID
    nickname: str
    avatar_url: str | None
    phone_masked: str | None
    status: UserStatus
    provider_names: list[IdentityProvider]
    order_count: int
    entitlement_count: int
    created_at: datetime


class UserAdminListResponse(BaseModel):
    items: list[UserAdminRead]
    total: int
    page: int
    page_size: int
