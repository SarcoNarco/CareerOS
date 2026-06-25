from __future__ import annotations

import re
from dataclasses import dataclass
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from careeros.db.models.internship import Internship, InternshipSkillRequirement
from careeros.db.models.matching import InternshipMatch
from careeros.db.models.profile import Profile
from careeros.db.models.verification import ApprovedClaim, ClaimStatus


@dataclass(slots=True)
class SelectedClaim:
    claim: ApprovedClaim
    relevance_score: float
    matched_signals: list[str]


def select_resume_claims(
    *,
    session: Session,
    profile_id: UUID,
    internship_id: UUID | None,
    max_claims: int,
) -> list[SelectedClaim]:
    profile = session.scalar(select(Profile).where(Profile.id == profile_id))
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found.")

    internship = _get_internship(session=session, internship_id=internship_id)
    match = _get_latest_match(session=session, profile_id=profile_id, internship_id=internship_id)
    claims = list(
        session.scalars(
            select(ApprovedClaim)
            .where(
                ApprovedClaim.profile_id == profile_id,
                ApprovedClaim.status == ClaimStatus.APPROVED,
                ApprovedClaim.retired_at.is_(None),
            )
            .order_by(ApprovedClaim.approved_at.desc(), ApprovedClaim.id.asc())
        )
    )
    if not claims:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No approved claims found for profile.",
        )

    internship_skills = _internship_skill_terms(internship)
    title_terms = _title_terms(internship)
    match_terms = _match_signal_terms(match)
    selected = [
        _score_claim(
            claim=claim,
            internship_skills=internship_skills,
            title_terms=title_terms,
            match_terms=match_terms,
        )
        for claim in claims
    ]
    selected.sort(
        key=lambda item: (
            item.relevance_score,
            _section_priority(item.claim),
            item.claim.approved_at,
        ),
        reverse=True,
    )
    return selected[:max_claims]


def _get_internship(session: Session, internship_id: UUID | None) -> Internship | None:
    if internship_id is None:
        return None
    internship = session.scalar(
        select(Internship)
        .options(
            selectinload(Internship.normalized_title_ref),
            selectinload(Internship.skill_requirements).selectinload(
                InternshipSkillRequirement.skill
            ),
        )
        .where(Internship.id == internship_id)
    )
    if internship is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Internship not found.")
    return internship


def _get_latest_match(
    *,
    session: Session,
    profile_id: UUID,
    internship_id: UUID | None,
) -> InternshipMatch | None:
    if internship_id is None:
        return None
    return session.scalar(
        select(InternshipMatch)
        .where(
            InternshipMatch.profile_id == profile_id,
            InternshipMatch.internship_id == internship_id,
        )
        .order_by(InternshipMatch.created_at.desc(), InternshipMatch.id.desc())
        .limit(1)
    )


def _score_claim(
    *,
    claim: ApprovedClaim,
    internship_skills: set[str],
    title_terms: set[str],
    match_terms: set[str],
) -> SelectedClaim:
    claim_text = claim.claim_text.casefold()
    claim_terms = _tokenize(claim.claim_text)
    score = 1.0
    signals: list[str] = []

    skill_hits = sorted(term for term in internship_skills if _contains_term(claim_text, term))
    if skill_hits:
        score += 6.0 + min(len(skill_hits), 5)
        signals.extend(f"skill:{term}" for term in skill_hits[:6])

    title_hits = sorted(claim_terms & title_terms)
    if title_hits:
        score += 0.5 + min(len(title_hits), 3) * 0.25
        signals.extend(f"title:{term}" for term in title_hits[:4])

    match_hits = sorted(claim_terms & match_terms)
    if match_hits:
        score += 3.0 + min(len(match_hits), 5) * 0.5
        signals.extend(f"match:{term}" for term in match_hits[:8])

    if claim.claim_type == "skill":
        score += 0.5
    if claim.owning_entity_type in {"project", "experience"}:
        score += 2.5

    return SelectedClaim(claim=claim, relevance_score=score, matched_signals=signals)


def _internship_skill_terms(internship: Internship | None) -> set[str]:
    if internship is None:
        return set()
    terms: set[str] = set()
    for requirement in internship.skill_requirements:
        skill_name = requirement.skill.name if requirement.skill is not None else requirement.skill_name_raw
        terms.add(skill_name.casefold())
    return terms


def _title_terms(internship: Internship | None) -> set[str]:
    if internship is None:
        return set()
    parts = [
        internship.title,
        internship.normalized_title,
        internship.normalized_title_ref.role_family if internship.normalized_title_ref else "",
    ]
    return set().union(*(_tokenize(part) for part in parts if part))


def _match_signal_terms(match: InternshipMatch | None) -> set[str]:
    if match is None:
        return set()
    signals = match.explanation_json.get("signals", {})
    values: list[str] = []
    for key in ("matched_skills", "matched_claim_terms", "role_matches"):
        raw_value = signals.get(key, [])
        if isinstance(raw_value, list):
            values.extend(str(item) for item in raw_value)
    return set().union(*(_tokenize(value) for value in values if value))


def _section_priority(claim: ApprovedClaim) -> int:
    return {
        "experience": 5,
        "project": 4,
        "education": 3,
        "skill": 2,
    }.get(claim.owning_entity_type, 1)


def _tokenize(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9+#.-]+", value.casefold())
        if len(token) > 1
    }


def _contains_term(text: str, term: str) -> bool:
    escaped = re.escape(term.casefold())
    return re.search(rf"(?<![a-z0-9]){escaped}(?![a-z0-9])", text) is not None
