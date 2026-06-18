from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from careeros.db.models.fact_staging import CandidateKind, VerificationStatus
from careeros.db.models.verification import ClaimStatus


class FactEvidenceSpanResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    source_document_id: UUID
    source_text_start: int
    source_text_end: int
    snippet_text: str
    created_at: datetime


class FactCandidateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    extraction_run_id: UUID
    profile_id: UUID
    candidate_kind: CandidateKind
    parent_candidate_id: UUID | None
    structured_data: dict[str, Any]
    status: VerificationStatus
    reviewer_notes: str | None
    created_at: datetime
    reviewed_at: datetime | None
    evidence_spans: list[FactEvidenceSpanResponse]


class FactCandidateListResponse(BaseModel):
    profile_id: UUID
    items: list[FactCandidateResponse]


class ApprovedClaimResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    profile_id: UUID
    owning_entity_type: str
    owning_entity_id: UUID | None
    claim_text: str
    claim_type: str
    status: ClaimStatus
    source_document_id: UUID
    source_primary_span_id: UUID | None
    approved_from_candidate_id: UUID | None
    approved_at: datetime
    retired_at: datetime | None
    created_at: datetime
    updated_at: datetime


class VerificationEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    fact_candidate_id: UUID | None
    approved_claim_id: UUID | None
    actor_user_id: UUID
    action: str
    notes: str | None
    created_at: datetime


class CandidateApproveRequest(BaseModel):
    notes: str | None = Field(default=None, max_length=4000)


class CandidateRejectRequest(BaseModel):
    notes: str | None = Field(default=None, max_length=4000)


class CandidateEditApproveRequest(BaseModel):
    claim_text: str = Field(min_length=1, max_length=4000)
    notes: str | None = Field(default=None, max_length=4000)


class CandidateReviewResponse(BaseModel):
    fact_candidate: FactCandidateResponse
    approved_claim: ApprovedClaimResponse | None
    verification_event: VerificationEventResponse
