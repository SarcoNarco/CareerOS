from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ProfileCreateRequest(BaseModel):
    display_name: str = Field(min_length=1, max_length=255)
    email: str | None = Field(default=None, max_length=320)
    timezone: str = Field(default="Asia/Kolkata", max_length=64)
    headline: str | None = Field(default=None, max_length=255)
    summary: str | None = None
    target_roles: list[str] = Field(default_factory=list)
    target_locations: list[str] = Field(default_factory=list)
    work_preferences: dict[str, Any] = Field(default_factory=dict)


class ProfileOwnerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str | None
    display_name: str
    timezone: str
    created_at: datetime
    updated_at: datetime


class ProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    headline: str | None
    summary: str | None
    target_roles: list[str]
    target_locations: list[str]
    work_preferences: dict[str, Any]
    created_at: datetime
    updated_at: datetime
    user: ProfileOwnerResponse

