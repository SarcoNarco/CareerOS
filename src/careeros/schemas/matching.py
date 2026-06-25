from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from careeros.db.models.fact_staging import ExtractionStatus
from careeros.schemas.internship import InternshipResponse


class MatchRecomputeRequest(BaseModel):
    profile_id: UUID
    limit: int | None = Field(default=None, ge=1, le=500)


class MatchRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    profile_id: UUID
    scoring_version: str
    embedding_version: str
    started_at: datetime
    completed_at: datetime | None
    status: ExtractionStatus


class InternshipMatchResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    match_run_id: UUID
    profile_id: UUID
    internship_id: UUID
    total_score: Decimal
    hard_filter_passed: bool
    normalized_feature_score: Decimal
    semantic_score: Decimal
    skill_score: Decimal
    experience_score: Decimal
    preference_score: Decimal
    gap_penalty: Decimal
    explanation_json: dict[str, Any]
    created_at: datetime
    internship: InternshipResponse | None = None


class MatchRecomputeResponse(BaseModel):
    match_run: MatchRunResponse
    matches: list[InternshipMatchResponse]


class InternshipMatchListResponse(BaseModel):
    items: list[InternshipMatchResponse]
