from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class TeacherBindCodeRead(BaseModel):
    code: str
    expires_at: datetime


class TeacherBindRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    code: str = Field(min_length=8, max_length=32)
    provider: str = Field(default="weapp", pattern="^(weapp|tt|h5)$")


class TeacherIdentityRead(BaseModel):
    teacher_id: UUID
    store_id: UUID
    teacher_name: str
    provider: str


class TeacherIdentityListResponse(BaseModel):
    items: list[TeacherIdentityRead]
