from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from careeros.db.base import utc_now
from careeros.db.models.fact_staging import CandidateKind, FactCandidate, VerificationStatus
from careeros.db.models.profile import Profile
from careeros.db.models.verification import ApprovedClaim, ClaimStatus, VerificationEvent


@dataclass(slots=True)
class VerificationOutcome:
    fact_candidate: FactCandidate
    approved_claim: ApprovedClaim | None
    verification_event: VerificationEvent


def list_fact_candidates(session: Session, profile_id: UUID) -> tuple[Profile, list[FactCandidate]]:
    profile = session.scalar(select(Profile).where(Profile.id == profile_id))
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found.",
        )

    candidates = list(
        session.scalars(
            select(FactCandidate)
            .options(selectinload(FactCandidate.evidence_spans))
            .where(FactCandidate.profile_id == profile_id)
            .order_by(FactCandidate.created_at.asc(), FactCandidate.id.asc())
        )
    )
    return profile, candidates


def approve_fact_candidate(
    session: Session,
    candidate_id: UUID,
    notes: str | None = None,
) -> VerificationOutcome:
    candidate = _get_reviewable_candidate(session=session, candidate_id=candidate_id)
    _assert_pending_candidate(candidate)

    actor_user_id = _get_actor_user_id(candidate)
    timestamp = utc_now()

    try:
        approved_claim = ApprovedClaim(
            profile_id=candidate.profile_id,
            owning_entity_type=_derive_owning_entity_type(candidate),
            owning_entity_id=None,
            claim_text=_derive_claim_text(candidate),
            claim_type=_derive_claim_type(candidate),
            status=ClaimStatus.APPROVED,
            source_document_id=candidate.extraction_run.source_document_id,
            source_primary_span_id=_get_primary_span_id(candidate),
            approved_from_candidate_id=candidate.id,
            approved_at=timestamp,
            retired_at=None,
        )
        session.add(approved_claim)

        candidate.status = VerificationStatus.APPROVED
        candidate.reviewer_notes = notes
        candidate.reviewed_at = timestamp
        session.flush()

        event = VerificationEvent(
            fact_candidate_id=candidate.id,
            approved_claim_id=approved_claim.id,
            actor_user_id=actor_user_id,
            action="approve",
            notes=notes,
            created_at=timestamp,
        )
        session.add(event)
        session.commit()
    except Exception:
        session.rollback()
        raise

    refreshed = _get_reviewable_candidate(session=session, candidate_id=candidate.id)
    claim = session.scalar(select(ApprovedClaim).where(ApprovedClaim.approved_from_candidate_id == candidate.id))
    if claim is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Approved claim was not created.")
    verification_event = session.scalar(
        select(VerificationEvent)
        .where(VerificationEvent.fact_candidate_id == candidate.id, VerificationEvent.action == "approve")
        .order_by(VerificationEvent.created_at.desc())
    )
    if verification_event is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Verification event was not created.")
    return VerificationOutcome(
        fact_candidate=refreshed,
        approved_claim=claim,
        verification_event=verification_event,
    )


def reject_fact_candidate(
    session: Session,
    candidate_id: UUID,
    notes: str | None = None,
) -> VerificationOutcome:
    candidate = _get_reviewable_candidate(session=session, candidate_id=candidate_id)
    _assert_pending_candidate(candidate)

    timestamp = utc_now()
    actor_user_id = _get_actor_user_id(candidate)

    try:
        candidate.status = VerificationStatus.REJECTED
        candidate.reviewer_notes = notes
        candidate.reviewed_at = timestamp
        session.flush()

        event = VerificationEvent(
            fact_candidate_id=candidate.id,
            approved_claim_id=None,
            actor_user_id=actor_user_id,
            action="reject",
            notes=notes,
            created_at=timestamp,
        )
        session.add(event)
        session.commit()
    except Exception:
        session.rollback()
        raise

    refreshed = _get_reviewable_candidate(session=session, candidate_id=candidate.id)
    verification_event = session.scalar(
        select(VerificationEvent)
        .where(VerificationEvent.fact_candidate_id == candidate.id, VerificationEvent.action == "reject")
        .order_by(VerificationEvent.created_at.desc())
    )
    if verification_event is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Verification event was not created.")
    return VerificationOutcome(
        fact_candidate=refreshed,
        approved_claim=None,
        verification_event=verification_event,
    )


def edit_and_approve_fact_candidate(
    session: Session,
    candidate_id: UUID,
    claim_text: str,
    notes: str | None = None,
) -> VerificationOutcome:
    candidate = _get_reviewable_candidate(session=session, candidate_id=candidate_id)
    _assert_pending_candidate(candidate)

    timestamp = utc_now()
    actor_user_id = _get_actor_user_id(candidate)

    try:
        approved_claim = ApprovedClaim(
            profile_id=candidate.profile_id,
            owning_entity_type=_derive_owning_entity_type(candidate),
            owning_entity_id=None,
            claim_text=claim_text.strip(),
            claim_type=_derive_claim_type(candidate),
            status=ClaimStatus.APPROVED,
            source_document_id=candidate.extraction_run.source_document_id,
            source_primary_span_id=_get_primary_span_id(candidate),
            approved_from_candidate_id=candidate.id,
            approved_at=timestamp,
            retired_at=None,
        )
        session.add(approved_claim)

        candidate.status = VerificationStatus.EDITED
        candidate.reviewer_notes = notes
        candidate.reviewed_at = timestamp
        session.flush()

        event = VerificationEvent(
            fact_candidate_id=candidate.id,
            approved_claim_id=approved_claim.id,
            actor_user_id=actor_user_id,
            action="edit_and_approve",
            notes=notes,
            created_at=timestamp,
        )
        session.add(event)
        session.commit()
    except Exception:
        session.rollback()
        raise

    refreshed = _get_reviewable_candidate(session=session, candidate_id=candidate.id)
    claim = session.scalar(select(ApprovedClaim).where(ApprovedClaim.approved_from_candidate_id == candidate.id))
    if claim is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Approved claim was not created.")
    verification_event = session.scalar(
        select(VerificationEvent)
        .where(VerificationEvent.fact_candidate_id == candidate.id, VerificationEvent.action == "edit_and_approve")
        .order_by(VerificationEvent.created_at.desc())
    )
    if verification_event is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Verification event was not created.")
    return VerificationOutcome(
        fact_candidate=refreshed,
        approved_claim=claim,
        verification_event=verification_event,
    )


def _get_reviewable_candidate(session: Session, candidate_id: UUID) -> FactCandidate:
    candidate = session.scalar(
        select(FactCandidate)
        .options(
            selectinload(FactCandidate.evidence_spans),
            selectinload(FactCandidate.extraction_run),
            selectinload(FactCandidate.parent_candidate),
        )
        .where(FactCandidate.id == candidate_id)
    )
    if candidate is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Fact candidate not found.",
        )

    if candidate.profile.user_id != candidate.extraction_run.source_document.user_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Fact candidate ownership is inconsistent.",
        )
    return candidate


def _assert_pending_candidate(candidate: FactCandidate) -> None:
    if candidate.status != VerificationStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Fact candidate has already been reviewed.",
        )


def _derive_claim_text(candidate: FactCandidate) -> str:
    if candidate.candidate_kind == CandidateKind.CLAIM:
        claim_text = str(candidate.structured_data.get("claim_text", "")).strip()
        if claim_text:
            return claim_text
    if candidate.candidate_kind == CandidateKind.SKILL:
        skill_name = str(candidate.structured_data.get("skill_name", "")).strip()
        if skill_name:
            return skill_name
    for key in ("summary", "name", "institution_name", "raw_text"):
        value = str(candidate.structured_data.get(key, "")).strip()
        if value:
            return value
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail="Fact candidate cannot be promoted because no claim text could be derived.",
    )


def _derive_claim_type(candidate: FactCandidate) -> str:
    mapping = {
        CandidateKind.CLAIM: "claim",
        CandidateKind.SKILL: "skill",
        CandidateKind.PROJECT: "summary",
        CandidateKind.EDUCATION: "summary",
    }
    return mapping.get(candidate.candidate_kind, "summary")


def _derive_owning_entity_type(candidate: FactCandidate) -> str:
    if candidate.parent_candidate is not None:
        return candidate.parent_candidate.candidate_kind.value
    return candidate.candidate_kind.value


def _get_primary_span_id(candidate: FactCandidate) -> UUID | None:
    if not candidate.evidence_spans:
        return None
    primary_span = min(candidate.evidence_spans, key=lambda span: (span.source_text_start, span.id))
    return primary_span.id


def _get_actor_user_id(candidate: FactCandidate) -> UUID:
    return candidate.profile.user_id
