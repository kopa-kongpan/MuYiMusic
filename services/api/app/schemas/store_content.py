from datetime import datetime
from enum import StrEnum
from urllib.parse import urlparse
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.store_content import (
    ContentBlockStatus,
    ContentBlockType,
    ContentJumpType,
)
from app.schemas.store import StorePublicRead


def validate_jump_target(jump_type: ContentJumpType, jump_target: str | None) -> None:
    if jump_type == ContentJumpType.NONE:
        if jump_target:
            raise ValueError("无跳转类型不能设置跳转目标")
        return
    if not jump_target:
        raise ValueError("启用跳转时必须设置跳转目标")
    if jump_type == ContentJumpType.INTERNAL and not jump_target.startswith("/pages/"):
        raise ValueError("小程序页面路径必须以 /pages/ 开头")
    if jump_type == ContentJumpType.WEB_URL:
        parsed = urlparse(jump_target)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("网页地址必须是完整的 HTTP 或 HTTPS 地址")


def validate_display_window(
    starts_at: datetime | None,
    ends_at: datetime | None,
) -> None:
    for value in (starts_at, ends_at):
        if value is not None and value.tzinfo is None:
            raise ValueError("展示时间必须包含时区")
    if starts_at is not None and ends_at is not None and starts_at >= ends_at:
        raise ValueError("展示结束时间必须晚于开始时间")


class ContentBlockCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    block_type: ContentBlockType
    title: str = Field(min_length=1, max_length=128)
    media_object_key: str | None = Field(default=None, max_length=1024)
    jump_type: ContentJumpType = ContentJumpType.NONE
    jump_target: str | None = Field(default=None, max_length=500)
    sort_order: int = Field(default=0, ge=0, le=9999)
    status: ContentBlockStatus = ContentBlockStatus.ENABLED
    starts_at: datetime | None = None
    ends_at: datetime | None = None

    @model_validator(mode="after")
    def validate_content(self) -> "ContentBlockCreate":
        if self.block_type != ContentBlockType.SHORTCUT and not self.media_object_key:
            raise ValueError("图片或视频内容必须设置媒体对象")
        if (
            self.block_type == ContentBlockType.SHORTCUT
            and self.jump_type == ContentJumpType.NONE
        ):
            raise ValueError("快捷入口必须设置跳转目标")
        validate_jump_target(self.jump_type, self.jump_target)
        validate_display_window(self.starts_at, self.ends_at)
        return self


class ContentBlockUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    block_type: ContentBlockType | None = None
    title: str | None = Field(default=None, min_length=1, max_length=128)
    media_object_key: str | None = Field(default=None, max_length=1024)
    jump_type: ContentJumpType | None = None
    jump_target: str | None = Field(default=None, max_length=500)
    sort_order: int | None = Field(default=None, ge=0, le=9999)
    status: ContentBlockStatus | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None


class ContentBlockRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    store_id: UUID
    block_type: ContentBlockType
    title: str
    media_object_key: str | None
    media_url: str | None = None
    jump_type: ContentJumpType
    jump_target: str | None
    sort_order: int
    status: ContentBlockStatus
    starts_at: datetime | None
    ends_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ContentBlockAdminListResponse(BaseModel):
    items: list[ContentBlockRead]
    total: int
    page: int
    page_size: int


class ContentBlockPublicRead(BaseModel):
    id: UUID
    block_type: ContentBlockType
    title: str
    media_url: str | None
    jump_type: ContentJumpType
    jump_target: str | None
    sort_order: int


class ContentOrderItem(BaseModel):
    id: UUID
    sort_order: int = Field(ge=0, le=9999)


class ContentOrderUpdate(BaseModel):
    items: list[ContentOrderItem] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def validate_unique_ids(self) -> "ContentOrderUpdate":
        ids = [item.id for item in self.items]
        if len(ids) != len(set(ids)):
            raise ValueError("排序内容不能重复")
        return self


class StoreHomeResponse(BaseModel):
    store: StorePublicRead
    content_blocks: list[ContentBlockPublicRead]


class UploadTicketRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    store_id: UUID
    file_name: str = Field(min_length=1, max_length=255)
    content_type: str = Field(min_length=3, max_length=128)
    file_size: int = Field(gt=0)
    purpose: "UploadPurpose" = Field(default_factory=lambda: UploadPurpose.HOME_CONTENT)


class UploadTicketResponse(BaseModel):
    object_key: str
    upload_url: str
    method: str = "PUT"
    headers: dict[str, str]
    public_url: str | None
    expires_at: datetime
    max_size_bytes: int


class UploadPurpose(StrEnum):
    HOME_CONTENT = "home_content"
    PRODUCT = "product"


UploadTicketRequest.model_rebuild()
