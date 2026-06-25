from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from careeros.db.models.application import ApplicationStatus
from careeros.schemas.internship import InternshipResponse
from careeros.schemas.matching import InternshipMatchResponse


class ApplicationCreateRequest(BaseModel):
    profile_id: UUID
    internship_id: UUID
    internship_match_id: UUID | None = None
    status: ApplicationStatus = ApplicationStatus.SAVED
    priority: int = Field(default=3, ge=1, le=5)
    notes: str | None = Field(default=None, max_length=4000)
    applied_at: datetime | None = None
    next_action_at: datetime | None = None


class ApplicationUpdateRequest(BaseModel):
    status: ApplicationStatus | None = None
    priority: int | None = Field(default=None, ge=1, le=5)
    notes: str | None = Field(default=None, max_length=4000)
    applied_at: datetime | None = None
    next_action_at: datetime | None = None


class ApplicationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    profile_id: UUID
    internship_id: UUID
    internship_match_id: UUID | None
    status: ApplicationStatus
    priority: int
    notes: str | None
    applied_at: datetime | None
    next_action_at: datetime | None
    created_at: datetime
    updated_at: datetime
    internship: InternshipResponse | None = None
    internship_match: InternshipMatchResponse | None = None


class ApplicationListResponse(BaseModel):
    items: list[ApplicationResponse]
