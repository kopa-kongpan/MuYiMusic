from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AdminLoginRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=12, max_length=256)


class AdminProfile(BaseModel):
    id: UUID
    username: str
    permissions: list[str]


class AdminTokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
    admin: AdminProfile
