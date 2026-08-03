from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.store import StoreStatus


class StoreCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=2, max_length=128)
    city: str = Field(min_length=2, max_length=64)
    district: str = Field(default="", max_length=64)
    address: str = Field(min_length=4, max_length=500)
    phone: str = Field(min_length=5, max_length=32)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    status: StoreStatus = StoreStatus.ACTIVE
    sort_order: int = Field(default=0, ge=0, le=9999)


class StoreUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str | None = Field(default=None, min_length=2, max_length=128)
    city: str | None = Field(default=None, min_length=2, max_length=64)
    district: str | None = Field(default=None, max_length=64)
    address: str | None = Field(default=None, min_length=4, max_length=500)
    phone: str | None = Field(default=None, min_length=5, max_length=32)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    status: StoreStatus | None = None
    sort_order: int | None = Field(default=None, ge=0, le=9999)


class StoreRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    city: str
    district: str
    address: str
    phone: str
    latitude: float
    longitude: float
    status: StoreStatus
    sort_order: int
    created_at: datetime
    updated_at: datetime


class StorePublicRead(StoreRead):
    distance_km: float | None = None


class StoreAdminListResponse(BaseModel):
    items: list[StoreRead]
    total: int
    page: int
    page_size: int


class StorePublicListResponse(BaseModel):
    items: list[StorePublicRead]
