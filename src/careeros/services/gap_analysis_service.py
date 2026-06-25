from __future__ import annotations

import re
from dataclasses import dataclass
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from careeros.db.base import utc_now
from careeros.db.models.internship import (
    Internship,
    InternshipSkillRequirement,
    SkillAlias,
)
from careeros.db.models.matching import InternshipMatch, SkillGapItem
from careeros.db.models.verification import ApprovedClaim, ClaimStatus


@dataclass(slots=True)
class CoveredSkill:
    skill_id: UUID | None
    skill_name: str
    reason: str


@dataclass(slots=True)
class MatchGapAnalysis:
    match: InternshipMatch
    missing_skills: list[SkillGapItem]
    covered_skills: list[CoveredSkill]


@dataclass(slots=True)
class ProfileSkillSet:
    skill_ids: set[UUID]
    normalized_names: set[str]


def analyze_match_gaps(session: Session, match_id: UUID) -> MatchGapAnalysis:
    match = _get_match(session=session, match_id=match_id)
    internship = _get_internship_with_skills(session=session, internship_id=match.internship_id)
    profile_skills = collect_profile_skills(session=session, profile_id=match.profile_id)

    requirements = _collapse_requirements(internship.skill_requirements)
    missing: list[SkillGapItem] = []
    covered: list[CoveredSkill] = []
    missing_keys: set[tuple[UUID | None, str]] = set()

    existing = {
        _gap_key(gap.skill_id, gap.skill_name_raw): gap
        for gap in session.scalars(
            select(SkillGapItem)
            .options(selectinload(SkillGapItem.skill))
            .where(SkillGapItem.internship_match_id == match_id)
        )
    }

    for requirement in requirements:
        skill_name = _requirement_name(requirement)
        if _is_requirement_covered(requirement=requirement, profile_skills=profile_skills):
            covered.append(
                CoveredSkill(
                    skill_id=requirement.skill_id,
                    skill_name=skill_name,
                    reason=f"Approved profile claims already mention {skill_name}.",
                )
            )
            continue

        key = _gap_key(requirement.skill_id, skill_name)
        missing_keys.add(key)
        severity = _severity(requirement=requirement, match=match)
        reason = _missing_reason(requirement=requirement, skill_name=skill_name, match=match)
        recommendation = _recommendation(skill_name=skill_name, severity=severity)
        gap = existing.get(key)
        if gap is None:
            gap = SkillGapItem(
                internship_match_id=match.id,
                skill_id=requirement.skill_id,
                skill_name_raw=skill_name,
                severity=severity,
                reason=reason,
                recommendation=recommendation,
                created_at=utc_now(),
            )
            session.add(gap)
        else:
            gap.severity = severity
            gap.reason = reason
            gap.recommendation = recommendation
        missing.append(gap)

    stale_ids = [
        gap.id for key, gap in existing.items()
        if key not in missing_keys
    ]
    if stale_ids:
        session.execute(delete(SkillGapItem).where(SkillGapItem.id.in_(stale_ids)))

    session.commit()
    for gap in missing:
        session.refresh(gap)
    return MatchGapAnalysis(match=match, missing_skills=missing, covered_skills=covered)


def list_profile_gap_items(session: Session, profile_id: UUID) -> list[SkillGapItem]:
    matches = list(
        session.scalars(
            select(InternshipMatch)
            .where(InternshipMatch.profile_id == profile_id)
            .order_by(InternshipMatch.total_score.desc(), InternshipMatch.created_at.desc())
        )
    )
    for match in matches:
        analyze_match_gaps(session=session, match_id=match.id)

    return list(
        session.scalars(
            select(SkillGapItem)
            .join(InternshipMatch, SkillGapItem.internship_match_id == InternshipMatch.id)
            .options(selectinload(SkillGapItem.skill))
            .where(InternshipMatch.profile_id == profile_id)
            .order_by(SkillGapItem.severity.desc(), SkillGapItem.created_at.desc())
        )
    )


def collect_profile_skills(session: Session, profile_id: UUID) -> ProfileSkillSet:
    claim_text = "\n".join(
        claim.claim_text
        for claim in session.scalars(
            select(ApprovedClaim).where(
                ApprovedClaim.profile_id == profile_id,
                ApprovedClaim.status == ClaimStatus.APPROVED,
                ApprovedClaim.retired_at.is_(None),
            )
        )
    )
    normalized_text = claim_text.casefold()
    skill_ids: set[UUID] = set()
    normalized_names: set[str] = set()

    aliases = list(
        session.scalars(select(SkillAlias).options(selectinload(SkillAlias.skill)))
    )
    for alias in aliases:
        if _contains_alias(normalized_text, alias.alias):
            skill_ids.add(alias.skill_id)
            normalized_names.add(_normalize(alias.skill.name))
            normalized_names.add(_normalize(alias.alias))

    return ProfileSkillSet(skill_ids=skill_ids, normalized_names=normalized_names)


def _get_match(session: Session, match_id: UUID) -> InternshipMatch:
    match = session.scalar(select(InternshipMatch).where(InternshipMatch.id == match_id))
    if match is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match not found.")
    return match


def _get_internship_with_skills(session: Session, internship_id: UUID) -> Internship:
    internship = session.scalar(
        select(Internship)
        .options(
            selectinload(Internship.skill_requirements).selectinload(
                InternshipSkillRequirement.skill
            )
        )
        .where(Internship.id == internship_id)
    )
    if internship is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Internship not found.")
    return internship


def _collapse_requirements(
    requirements: list[InternshipSkillRequirement],
) -> list[InternshipSkillRequirement]:
    strongest: dict[tuple[UUID | None, str], InternshipSkillRequirement] = {}
    for requirement in requirements:
        key = _gap_key(requirement.skill_id, _requirement_name(requirement))
        current = strongest.get(key)
        if current is None or requirement.requirement_strength > current.requirement_strength:
            strongest[key] = requirement
    return sorted(
        strongest.values(),
        key=lambda requirement: (
            requirement.is_required,
            requirement.requirement_strength,
            _requirement_name(requirement),
        ),
        reverse=True,
    )


def _is_requirement_covered(
    *,
    requirement: InternshipSkillRequirement,
    profile_skills: ProfileSkillSet,
) -> bool:
    if requirement.skill_id is not None and requirement.skill_id in profile_skills.skill_ids:
        return True
    return _normalize(_requirement_name(requirement)) in profile_skills.normalized_names


def _requirement_name(requirement: InternshipSkillRequirement) -> str:
    if requirement.skill is not None:
        return requirement.skill.name
    return requirement.skill_name_raw


def _severity(requirement: InternshipSkillRequirement, match: InternshipMatch) -> int:
    severity = max(1, min(5, requirement.requirement_strength))
    if requirement.is_required:
        severity = max(severity, 4)
    if float(match.total_score) >= 80:
        severity += 1
    elif float(match.total_score) >= 65 and requirement.is_required:
        severity += 1
    return max(1, min(5, severity))


def _missing_reason(
    *,
    requirement: InternshipSkillRequirement,
    skill_name: str,
    match: InternshipMatch,
) -> str:
    requirement_type = "required" if requirement.is_required else "preferred"
    return (
        f"{skill_name} appears as a {requirement_type} skill for this internship "
        f"and was not found in approved profile claims. Match score: {match.total_score}."
    )


def _recommendation(*, skill_name: str, severity: int) -> str:
    if severity >= 4:
        return f"Prioritize a small project or course that demonstrates {skill_name}."
    return f"Build basic familiarity with {skill_name} and add verified evidence when available."


def _gap_key(skill_id: UUID | None, skill_name: str) -> tuple[UUID | None, str]:
    return skill_id, _normalize(skill_name)


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value.casefold().strip())


def _contains_alias(text: str, alias: str) -> bool:
    escaped = re.escape(alias.casefold())
    pattern = rf"(?<![a-z0-9]){escaped}(?![a-z0-9])"
    return re.search(pattern, text) is not None
