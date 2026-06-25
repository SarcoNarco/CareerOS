from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from careeros.db.models.internship import (
    IngestionRunStatus,
    InternshipStatus,
    SourcePolicyStatus,
    SourceType,
    WorkMode,
)


class SourceCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    source_type: SourceType = SourceType.MANUAL
    base_url: HttpUrl | None = None
    is_active: bool = True
    policy_status: SourcePolicyStatus = SourcePolicyStatus.ALLOWED
    policy_notes: str | None = Field(default=None, max_length=4000)


class SourcePolicyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    source_id: UUID
    policy_status: SourcePolicyStatus
    robots_checked_at: datetime | None
    terms_reviewed_at: datetime | None
    rate_limit_notes: str | None
    notes: str | None
    updated_at: datetime


class SourceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    source_type: SourceType
    base_url: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    policy: SourcePolicyResponse | None


class ManualPostingPayload(BaseModel):
    external_id: str | None = Field(default=None, max_length=255)
    source_url: HttpUrl | None = None
    title: str = Field(min_length=1, max_length=255)
    company_name: str = Field(min_length=1, max_length=255)
    company_domain: str | None = Field(default=None, max_length=255)
    description: str = Field(min_length=1)
    requirements: str | None = None
    responsibilities: str | None = None
    application_url: HttpUrl
    location: str | None = Field(default=None, max_length=255)
    work_mode: str | None = Field(default=None, max_length=64)
    posted_at: datetime | None = None
    expires_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SourceIngestRequest(BaseModel):
    postings: list[ManualPostingPayload] = Field(min_length=1, max_length=100)


class IngestionRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    source_id: UUID
    started_at: datetime
    completed_at: datetime | None
    status: IngestionRunStatus
    items_seen: int
    items_created: int
    items_updated: int
    error_message: str | None
    metadata_json: dict[str, Any]


class InternshipResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    source_id: UUID
    raw_posting_id: UUID
    title: str
    normalized_title_id: UUID | None
    normalized_title: str
    company_name: str
    company_domain: str | None
    description: str
    requirements: str | None
    responsibilities: str | None
    application_url: str
    location_text: str | None
    normalized_location_id: UUID | None
    normalized_location: str | None
    work_mode: WorkMode
    posted_at: datetime | None
    expires_at: datetime | None
    status: InternshipStatus
    dedupe_key: str
    content_hash: str
    created_at: datetime
    updated_at: datetime


class SourceIngestResponse(BaseModel):
    ingestion_run: IngestionRunResponse
    created_internships: list[InternshipResponse]
    duplicate_count: int


class InternshipListResponse(BaseModel):
    items: list[InternshipResponse]


class SkillAliasResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    skill_id: UUID
    alias: str
    normalization_source: str
    created_at: datetime


class SkillResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    category: str
    created_at: datetime
    aliases: list[SkillAliasResponse] = Field(default_factory=list)


class SkillListResponse(BaseModel):
    items: list[SkillResponse]


class NormalizedTitleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    canonical_title: str
    role_family: str
    created_at: datetime


class NormalizedLocationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    country: str | None
    city: str | None
    region: str | None
    work_mode: WorkMode
    canonical_label: str
    created_at: datetime


class InternshipSkillRequirementResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    internship_id: UUID
    skill_id: UUID | None
    skill_name_raw: str
    requirement_strength: int
    is_required: bool
    extraction_method: str
    created_at: datetime
    skill: SkillResponse | None


class InternshipSkillRequirementListResponse(BaseModel):
    internship_id: UUID
    items: list[InternshipSkillRequirementResponse]


class InternshipNormalizeResponse(BaseModel):
    internship: InternshipResponse
    normalized_title: NormalizedTitleResponse
    normalized_location: NormalizedLocationResponse
    skill_requirements: list[InternshipSkillRequirementResponse]
