from __future__ import annotations

import re
from dataclasses import dataclass
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from careeros.db.models.internship import (
    Internship,
    InternshipSkillRequirement,
    SkillAlias,
    WorkMode,
)
from careeros.db.models.profile import Profile
from careeros.db.models.verification import ApprovedClaim, ClaimStatus


_TOKEN_RE = re.compile(r"[a-z0-9+#.-]+")
_STOPWORDS = {
    "a",
    "an",
    "and",
    "for",
    "in",
    "of",
    "on",
    "the",
    "to",
    "with",
}


@dataclass(slots=True)
class ProfileFeatures:
    profile_id: UUID
    approved_claims: list[ApprovedClaim]
    claim_text: str
    skill_names: set[str]
    target_roles: set[str]
    target_locations: set[str]
    tokens: set[str]


@dataclass(slots=True)
class InternshipFeatures:
    internship: Internship
    text: str
    skill_names: set[str]
    normalized_title: str | None
    role_family: str | None
    normalized_location: str | None
    work_mode: WorkMode
    tokens: set[str]


def build_profile_features(session: Session, profile_id: UUID) -> ProfileFeatures:
    profile = session.scalar(select(Profile).where(Profile.id == profile_id))
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found.",
        )

    claims = list(
        session.scalars(
            select(ApprovedClaim)
            .where(
                ApprovedClaim.profile_id == profile_id,
                ApprovedClaim.status == ClaimStatus.APPROVED,
                ApprovedClaim.retired_at.is_(None),
            )
            .order_by(ApprovedClaim.created_at.asc(), ApprovedClaim.id.asc())
        )
    )
    if not claims:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No approved claims found for profile.",
        )

    claim_text = "\n".join(claim.claim_text for claim in claims)
    return ProfileFeatures(
        profile_id=profile.id,
        approved_claims=claims,
        claim_text=claim_text,
        skill_names=_extract_skill_names_from_text(session=session, text=claim_text),
        target_roles={_normalize_value(role) for role in profile.target_roles},
        target_locations={_normalize_value(location) for location in profile.target_locations},
        tokens=_tokenize(claim_text),
    )


def build_internship_features(internship: Internship) -> InternshipFeatures:
    skill_names = {
        _normalize_value(requirement.skill.name if requirement.skill else requirement.skill_name_raw)
        for requirement in internship.skill_requirements
    }
    text = "\n".join(
        part
        for part in (
            internship.title,
            internship.normalized_title,
            internship.company_name,
            internship.location_text,
            internship.normalized_location,
            internship.description,
            internship.requirements,
            internship.responsibilities,
            " ".join(sorted(skill_names)),
        )
        if part
    )
    return InternshipFeatures(
        internship=internship,
        text=text,
        skill_names=skill_names,
        normalized_title=_normalize_value(internship.normalized_title),
        role_family=(
            _normalize_value(internship.normalized_title_ref.role_family)
            if internship.normalized_title_ref is not None
            else None
        ),
        normalized_location=(
            _normalize_value(internship.normalized_location)
            if internship.normalized_location
            else None
        ),
        work_mode=internship.work_mode,
        tokens=_tokenize(text),
    )


def build_all_internship_features(
    session: Session,
    internship_ids: set[UUID] | None = None,
) -> list[InternshipFeatures]:
    statement = select(Internship).options(
        selectinload(Internship.normalized_title_ref),
        selectinload(Internship.normalized_location_ref),
        selectinload(Internship.skill_requirements).selectinload(
            InternshipSkillRequirement.skill
        ),
    )
    if internship_ids is not None:
        if not internship_ids:
            return []
        statement = statement.where(Internship.id.in_(internship_ids))

    internships = list(
        session.scalars(statement.order_by(Internship.created_at.desc(), Internship.id.asc()))
    )
    return [build_internship_features(internship) for internship in internships]


def _extract_skill_names_from_text(session: Session, text: str) -> set[str]:
    normalized_text = text.casefold()
    skills: set[str] = set()
    aliases = list(
        session.scalars(
            select(SkillAlias).options(selectinload(SkillAlias.skill))
        )
    )
    for alias in aliases:
        if _contains_alias(normalized_text, alias.alias):
            skills.add(_normalize_value(alias.skill.name))
    return skills


def _contains_alias(text: str, alias: str) -> bool:
    escaped = re.escape(alias.casefold())
    pattern = rf"(?<![a-z0-9]){escaped}(?![a-z0-9])"
    return re.search(pattern, text) is not None


def _tokenize(text: str) -> set[str]:
    return {
        token
        for token in _TOKEN_RE.findall(text.casefold())
        if token and token not in _STOPWORDS and len(token) > 1
    }


def _normalize_value(value: str) -> str:
    return re.sub(r"\s+", " ", value.casefold().strip())
