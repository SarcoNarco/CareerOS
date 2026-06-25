from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from careeros.api.deps import get_db_session, require_api_token
from careeros.schemas.gap_analysis import (
    CoveredSkillResponse,
    MarketTopSkillResponse,
    MarketTopSkillsResponse,
    MatchGapAnalysisResponse,
    ProfileSkillGapsResponse,
    ProfileSkillRecommendationsResponse,
    SkillGapItemResponse,
    SkillRecommendationResponse,
)
from careeros.services.gap_analysis_service import analyze_match_gaps, list_profile_gap_items
from careeros.services.learning_recommender import recommend_profile_skills
from careeros.services.market_intelligence_service import get_top_market_skills

router = APIRouter(tags=["gap-analysis"])


@router.get(
    "/matches/{match_id}/gaps",
    response_model=MatchGapAnalysisResponse,
    dependencies=[Depends(require_api_token)],
)
def get_match_gaps_endpoint(
    match_id: UUID,
    session: Session = Depends(get_db_session),
) -> MatchGapAnalysisResponse:
    analysis = analyze_match_gaps(session=session, match_id=match_id)
    return MatchGapAnalysisResponse(
        match_id=analysis.match.id,
        profile_id=analysis.match.profile_id,
        internship_id=analysis.match.internship_id,
        missing_skills=[
            SkillGapItemResponse.model_validate(item)
            for item in analysis.missing_skills
        ],
        covered_skills=[
            CoveredSkillResponse(
                skill_id=item.skill_id,
                skill_name=item.skill_name,
                reason=item.reason,
            )
            for item in analysis.covered_skills
        ],
    )


@router.get(
    "/profiles/{profile_id}/skill-gaps",
    response_model=ProfileSkillGapsResponse,
    dependencies=[Depends(require_api_token)],
)
def get_profile_skill_gaps_endpoint(
    profile_id: UUID,
    session: Session = Depends(get_db_session),
) -> ProfileSkillGapsResponse:
    items = list_profile_gap_items(session=session, profile_id=profile_id)
    return ProfileSkillGapsResponse(
        profile_id=profile_id,
        items=[SkillGapItemResponse.model_validate(item) for item in items],
    )


@router.get(
    "/profiles/{profile_id}/recommendations",
    response_model=ProfileSkillRecommendationsResponse,
    dependencies=[Depends(require_api_token)],
)
def get_profile_recommendations_endpoint(
    profile_id: UUID,
    limit: int = Query(default=10, ge=1, le=50),
    session: Session = Depends(get_db_session),
) -> ProfileSkillRecommendationsResponse:
    items = recommend_profile_skills(session=session, profile_id=profile_id, limit=limit)
    return ProfileSkillRecommendationsResponse(
        profile_id=profile_id,
        items=[
            SkillRecommendationResponse(
                skill_id=item.skill_id,
                skill_name=item.skill_name,
                priority_score=item.priority_score,
                demand_count=item.demand_count,
                matched_internship_count=item.matched_internship_count,
                reason=item.reason,
                recommendation=item.recommendation,
            )
            for item in items
        ],
    )


@router.get(
    "/market/top-skills",
    response_model=MarketTopSkillsResponse,
    dependencies=[Depends(require_api_token)],
)
def get_market_top_skills_endpoint(
    limit: int = Query(default=20, ge=1, le=100),
    session: Session = Depends(get_db_session),
) -> MarketTopSkillsResponse:
    aggregate = get_top_market_skills(session=session, limit=limit)
    return _market_response(aggregate)


@router.get(
    "/market/top-skills/{role_family}",
    response_model=MarketTopSkillsResponse,
    dependencies=[Depends(require_api_token)],
)
def get_market_top_skills_by_role_endpoint(
    role_family: str,
    limit: int = Query(default=20, ge=1, le=100),
    session: Session = Depends(get_db_session),
) -> MarketTopSkillsResponse:
    aggregate = get_top_market_skills(
        session=session,
        role_family=role_family,
        limit=limit,
    )
    return _market_response(aggregate)


def _market_response(aggregate) -> MarketTopSkillsResponse:
    return MarketTopSkillsResponse(
        role_family=aggregate.role_family,
        total_internships=aggregate.total_internships,
        items=[
            MarketTopSkillResponse(
                skill_id=item.skill_id,
                skill_name=item.skill_name,
                internship_count=item.internship_count,
                percentage=item.percentage,
            )
            for item in aggregate.items
        ],
    )
