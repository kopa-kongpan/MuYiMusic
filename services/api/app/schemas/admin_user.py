from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AdminRoleRead(BaseModel):
    code: str
    name: str
    permissions: list[str]


class AdminStoreOption(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    city: str
    status: str


class AdminUserRead(BaseModel):
    id: UUID
    username: str
    is_active: bool
    roles: list[AdminRoleRead]
    stores: list[AdminStoreOption]
    created_at: datetime
    updated_at: datetime


class AdminUserListResponse(BaseModel):
    items: list[AdminUserRead]
    total: int
    page: int
    page_size: int


class AdminUserOptionsResponse(BaseModel):
    roles: list[AdminRoleRead]
    stores: list[AdminStoreOption]


class AdminUserCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=12, max_length=256)
    role_code: str = Field(min_length=1, max_length=64)
    store_ids: list[UUID] = Field(min_length=1, max_length=100)


class AdminUserUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    role_code: str | None = Field(default=None, min_length=1, max_length=64)
    store_ids: list[UUID] | None = Field(default=None, min_length=1, max_length=100)
    is_active: bool | None = None


class AdminUserPasswordReset(BaseModel):
    password: str = Field(min_length=12, max_length=256)
