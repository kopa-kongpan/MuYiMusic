from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class FranchisePageUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=128)
    introduction: str = Field(min_length=1, max_length=5000)
    advantages: str = Field(min_length=1, max_length=5000)
    support_policy: str = Field(min_length=1, max_length=5000)
    application_process: str = Field(min_length=1, max_length=5000)
    contact_name: str = Field(min_length=1, max_length=64)
    contact_phone: str = Field(min_length=1, max_length=32)
    contact_wechat: str | None = Field(default=None, max_length=64)
    is_published: bool = False


class FranchisePageRead(FranchisePageUpdate):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    store_id: UUID
    created_at: datetime
    updated_at: datetime


class FranchisePagePublicRead(BaseModel):
    title: str
    introduction: str
    advantages: str
    support_policy: str
    application_process: str
    contact_name: str
    contact_phone: str
    contact_wechat: str | None
