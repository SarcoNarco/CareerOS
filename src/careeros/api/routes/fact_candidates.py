from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from careeros.api.deps import get_db_session, require_api_token
from careeros.schemas.verification import (
    CandidateApproveRequest,
    CandidateEditApproveRequest,
    CandidateRejectRequest,
    CandidateReviewResponse,
    FactCandidateListResponse,
    FactCandidateResponse,
)
from careeros.services.verification_service import (
    approve_fact_candidate,
    edit_and_approve_fact_candidate,
    list_fact_candidates,
    reject_fact_candidate,
)

router = APIRouter(tags=["fact-candidates"])


@router.get(
    "/profiles/{profile_id}/fact-candidates",
    response_model=FactCandidateListResponse,
    dependencies=[Depends(require_api_token)],
)
def list_fact_candidates_endpoint(
    profile_id: UUID,
    session: Session = Depends(get_db_session),
) -> FactCandidateListResponse:
    profile, candidates = list_fact_candidates(session=session, profile_id=profile_id)
    return FactCandidateListResponse(
        profile_id=profile.id,
        items=[FactCandidateResponse.model_validate(candidate) for candidate in candidates],
    )


@router.post(
    "/fact-candidates/{candidate_id}/approve",
    response_model=CandidateReviewResponse,
    dependencies=[Depends(require_api_token)],
)
def approve_fact_candidate_endpoint(
    candidate_id: UUID,
    payload: CandidateApproveRequest,
    session: Session = Depends(get_db_session),
) -> CandidateReviewResponse:
    outcome = approve_fact_candidate(session=session, candidate_id=candidate_id, notes=payload.notes)
    return CandidateReviewResponse(
        fact_candidate=FactCandidateResponse.model_validate(outcome.fact_candidate),
        approved_claim=outcome.approved_claim and outcome.approved_claim,
        verification_event=outcome.verification_event,
    )


@router.post(
    "/fact-candidates/{candidate_id}/reject",
    response_model=CandidateReviewResponse,
    dependencies=[Depends(require_api_token)],
)
def reject_fact_candidate_endpoint(
    candidate_id: UUID,
    payload: CandidateRejectRequest,
    session: Session = Depends(get_db_session),
) -> CandidateReviewResponse:
    outcome = reject_fact_candidate(session=session, candidate_id=candidate_id, notes=payload.notes)
    return CandidateReviewResponse(
        fact_candidate=FactCandidateResponse.model_validate(outcome.fact_candidate),
        approved_claim=None,
        verification_event=outcome.verification_event,
    )


@router.post(
    "/fact-candidates/{candidate_id}/edit-and-approve",
    response_model=CandidateReviewResponse,
    dependencies=[Depends(require_api_token)],
)
def edit_and_approve_fact_candidate_endpoint(
    candidate_id: UUID,
    payload: CandidateEditApproveRequest,
    session: Session = Depends(get_db_session),
) -> CandidateReviewResponse:
    outcome = edit_and_approve_fact_candidate(
        session=session,
        candidate_id=candidate_id,
        claim_text=payload.claim_text,
        notes=payload.notes,
    )
    return CandidateReviewResponse(
        fact_candidate=FactCandidateResponse.model_validate(outcome.fact_candidate),
        approved_claim=outcome.approved_claim and outcome.approved_claim,
        verification_event=outcome.verification_event,
    )
