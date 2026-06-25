from __future__ import annotations

import re
from dataclasses import dataclass
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from careeros.db.models.internship import (
    Internship,
    InternshipSkillRequirement,
    SkillAlias,
    SkillCatalog,
)


_REQUIRED_CONTEXT_TERMS = (
    "required",
    "requirements",
    "required skills",
    "qualifications",
    "must have",
    "need to have",
    "you have",
    "experience with",
    "experience in",
    "proficiency",
    "tech stack",
    "technical skills",
)
_PREFERRED_CONTEXT_TERMS = (
    "preferred",
    "nice to have",
    "bonus",
    "familiarity",
    "plus",
)


@dataclass(slots=True)
class ExtractedSkillRequirement:
    skill: SkillCatalog
    skill_name_raw: str
    requirement_strength: int
    is_required: bool


def extract_skill_requirements(
    session: Session,
    internship: Internship,
) -> list[ExtractedSkillRequirement]:
    searchable_text = _build_searchable_text(internship)
    aliases = list(
        session.scalars(
            select(SkillAlias)
            .options(selectinload(SkillAlias.skill))
            .order_by(SkillAlias.alias.desc())
        )
    )

    by_skill_id: dict[UUID, ExtractedSkillRequirement] = {}
    for alias in aliases:
        if not _contains_alias(searchable_text, alias.alias):
            continue

        strength = _requirement_strength(searchable_text, alias.alias)
        is_required = strength >= 4
        existing = by_skill_id.get(alias.skill_id)
        if existing is None or strength > existing.requirement_strength:
            by_skill_id[alias.skill_id] = ExtractedSkillRequirement(
                skill=alias.skill,
                skill_name_raw=alias.alias,
                requirement_strength=strength,
                is_required=is_required,
            )

    return sorted(by_skill_id.values(), key=lambda item: item.skill.name.casefold())


def replace_internship_skill_requirements(
    session: Session,
    internship: Internship,
) -> list[InternshipSkillRequirement]:
    extracted = extract_skill_requirements(session=session, internship=internship)
    session.execute(
        delete(InternshipSkillRequirement).where(
            InternshipSkillRequirement.internship_id == internship.id
        )
    )

    requirements: list[InternshipSkillRequirement] = []
    for item in extracted:
        requirement = InternshipSkillRequirement(
            internship_id=internship.id,
            skill_id=item.skill.id,
            skill_name_raw=item.skill_name_raw,
            requirement_strength=item.requirement_strength,
            is_required=item.is_required,
            extraction_method="rules",
        )
        session.add(requirement)
        requirements.append(requirement)

    session.flush()
    return requirements


def list_internship_skill_requirements(
    session: Session,
    internship_id: UUID,
) -> tuple[Internship, list[InternshipSkillRequirement]]:
    internship = session.scalar(select(Internship).where(Internship.id == internship_id))
    if internship is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Internship not found.",
        )

    requirements = list(
        session.scalars(
            select(InternshipSkillRequirement)
            .options(selectinload(InternshipSkillRequirement.skill))
            .where(InternshipSkillRequirement.internship_id == internship_id)
            .order_by(InternshipSkillRequirement.requirement_strength.desc())
        )
    )
    return internship, requirements


def _build_searchable_text(internship: Internship) -> str:
    return "\n".join(
        part
        for part in (
            internship.title,
            internship.description,
            internship.requirements,
            internship.responsibilities,
            internship.normalized_title,
            internship.normalized_location,
        )
        if part
    ).casefold()


def _contains_alias(text: str, alias: str) -> bool:
    escaped = re.escape(alias.casefold())
    if len(alias) <= 2:
        pattern = rf"(?<![a-z0-9]){escaped}(?![a-z0-9])"
    else:
        pattern = rf"(?<![a-z0-9]){escaped}(?![a-z0-9])"
    return re.search(pattern, text) is not None


def _requirement_strength(text: str, alias: str) -> int:
    alias_position = text.find(alias.casefold())
    if alias_position == -1:
        return 1

    window_start = max(0, alias_position - 120)
    window_end = min(len(text), alias_position + len(alias) + 120)
    context = text[window_start:window_end]

    if any(term in context for term in _REQUIRED_CONTEXT_TERMS):
        return 5
    if any(term in context for term in _PREFERRED_CONTEXT_TERMS):
        return 3
    if any(term in text for term in ("requirements", "qualifications", "tech stack", "skills")):
        return 4
    return 3
