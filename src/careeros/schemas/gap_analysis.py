from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from careeros.schemas.internship import SkillResponse


class CoveredSkillResponse(BaseModel):
    skill_id: UUID | None
    skill_name: str
    reason: str


class SkillGapItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    internship_match_id: UUID
    skill_id: UUID | None
    skill_name_raw: str
    severity: int
    reason: str
    recommendation: str
    created_at: datetime
    skill: SkillResponse | None = None


class MatchGapAnalysisResponse(BaseModel):
    match_id: UUID
    profile_id: UUID
    internship_id: UUID
    missing_skills: list[SkillGapItemResponse]
    covered_skills: list[CoveredSkillResponse]


class ProfileSkillGapsResponse(BaseModel):
    profile_id: UUID
    items: list[SkillGapItemResponse]


class SkillRecommendationResponse(BaseModel):
    skill_id: UUID | None
    skill_name: str
    priority_score: Decimal
    demand_count: int
    matched_internship_count: int
    reason: str
    recommendation: str


class ProfileSkillRecommendationsResponse(BaseModel):
    profile_id: UUID
    items: list[SkillRecommendationResponse]


class MarketTopSkillResponse(BaseModel):
    skill_id: UUID | None
    skill_name: str
    internship_count: int
    percentage: Decimal


class MarketTopSkillsResponse(BaseModel):
    role_family: str | None = None
    total_internships: int
    items: list[MarketTopSkillResponse]
