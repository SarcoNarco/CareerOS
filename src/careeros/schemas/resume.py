from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from careeros.db.models.resume import ResumeStatus
from careeros.schemas.verification import ApprovedClaimResponse


class ResumeGenerateRequest(BaseModel):
    profile_id: UUID
    internship_id: UUID | None = None
    template_id: UUID | None = None
    max_claims: int = Field(default=12, ge=1, le=30)


class ResumeTemplateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    template_engine: str
    template_path: str
    is_active: bool
    created_at: datetime


class GeneratedResumeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    profile_id: UUID
    internship_id: UUID | None
    template_id: UUID
    status: ResumeStatus
    rendered_html_path: str | None
    rendered_pdf_path: str | None
    created_at: datetime
    template: ResumeTemplateResponse | None = None


class GeneratedResumeClaimResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    generated_resume_id: UUID
    approved_claim_id: UUID
    section_name: str
    display_order: int
    rendered_text: str
    created_at: datetime
    approved_claim: ApprovedClaimResponse | None = None


class GeneratedResumeDetailResponse(BaseModel):
    resume: GeneratedResumeResponse
    claims: list[GeneratedResumeClaimResponse]


class GeneratedResumeListResponse(BaseModel):
    items: list[GeneratedResumeResponse]


class GeneratedResumeClaimListResponse(BaseModel):
    resume_id: UUID
    items: list[GeneratedResumeClaimResponse]
