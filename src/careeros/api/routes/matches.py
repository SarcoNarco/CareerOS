from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from careeros.api.deps import (
    get_db_session,
    get_embedding_provider,
    get_settings,
    require_api_token,
)
from careeros.core.config import Settings
from careeros.db.models.internship import Internship
from careeros.db.models.matching import InternshipMatch
from careeros.schemas.internship import InternshipResponse
from careeros.schemas.matching import (
    InternshipMatchListResponse,
    InternshipMatchResponse,
    MatchRecomputeRequest,
    MatchRecomputeResponse,
    MatchRunResponse,
)
from careeros.services.embedding_provider import EmbeddingProvider
from careeros.services.matching_engine import (
    get_match,
    get_top_matches,
    list_matches,
    recompute_matches,
)

router = APIRouter(tags=["matches"])


@router.post(
    "/matches/recompute",
    response_model=MatchRecomputeResponse,
    dependencies=[Depends(require_api_token)],
)
def recompute_matches_endpoint(
    payload: MatchRecomputeRequest,
    session: Session = Depends(get_db_session),
    provider: EmbeddingProvider = Depends(get_embedding_provider),
    settings: Settings = Depends(get_settings),
) -> MatchRecomputeResponse:
    result = recompute_matches(
        session=session,
        profile_id=payload.profile_id,
        provider=provider,
        scoring_version=settings.scoring_version,
        limit=payload.limit,
    )
    return MatchRecomputeResponse(
        match_run=MatchRunResponse.model_validate(result.match_run),
        matches=[
            _match_response(session=session, match=match)
            for match in result.matches
        ],
    )


@router.get(
    "/matches",
    response_model=InternshipMatchListResponse,
    dependencies=[Depends(require_api_token)],
)
def list_matches_endpoint(
    profile_id: UUID | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    session: Session = Depends(get_db_session),
) -> InternshipMatchListResponse:
    matches = list_matches(session=session, profile_id=profile_id, limit=limit)
    return InternshipMatchListResponse(
        items=[_match_response(session=session, match=match) for match in matches]
    )


@router.get(
    "/matches/{match_id}",
    response_model=InternshipMatchResponse,
    dependencies=[Depends(require_api_token)],
)
def get_match_endpoint(
    match_id: UUID,
    session: Session = Depends(get_db_session),
) -> InternshipMatchResponse:
    match = get_match(session=session, match_id=match_id)
    return _match_response(session=session, match=match)


@router.get(
    "/profiles/{profile_id}/top-matches",
    response_model=InternshipMatchListResponse,
    dependencies=[Depends(require_api_token)],
)
def get_top_matches_endpoint(
    profile_id: UUID,
    limit: int = Query(default=10, ge=1, le=100),
    session: Session = Depends(get_db_session),
) -> InternshipMatchListResponse:
    matches = get_top_matches(session=session, profile_id=profile_id, limit=limit)
    return InternshipMatchListResponse(
        items=[_match_response(session=session, match=match) for match in matches]
    )


def _match_response(session: Session, match: InternshipMatch) -> InternshipMatchResponse:
    internship = session.scalar(select(Internship).where(Internship.id == match.internship_id))
    response = InternshipMatchResponse.model_validate(match)
    if internship is not None:
        response.internship = InternshipResponse.model_validate(internship)
    return response
