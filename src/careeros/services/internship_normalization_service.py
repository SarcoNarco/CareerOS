from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from careeros.db.models.internship import (
    Internship,
    InternshipSkillRequirement,
    NormalizedLocation,
    NormalizedTitle,
)
from careeros.services.location_normalizer import normalize_location_to_record
from careeros.services.skill_extractor import replace_internship_skill_requirements
from careeros.services.title_normalizer import normalize_title_to_record


@dataclass(slots=True)
class InternshipNormalizationOutcome:
    internship: Internship
    normalized_title: NormalizedTitle
    normalized_location: NormalizedLocation
    skill_requirements: list[InternshipSkillRequirement]


def normalize_internship(
    session: Session,
    internship_id: UUID,
) -> InternshipNormalizationOutcome:
    internship = session.scalar(select(Internship).where(Internship.id == internship_id))
    if internship is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Internship not found.",
        )

    normalized_title = normalize_title_to_record(session=session, raw_title=internship.title)
    normalized_location = normalize_location_to_record(
        session=session,
        location_text=internship.location_text,
        work_mode_text=internship.work_mode.value,
    )

    try:
        internship.normalized_title_id = normalized_title.id
        internship.normalized_title = normalized_title.canonical_title
        internship.normalized_location_id = normalized_location.id
        internship.normalized_location = normalized_location.canonical_label
        internship.work_mode = normalized_location.work_mode
        skill_requirements = replace_internship_skill_requirements(
            session=session,
            internship=internship,
        )
        session.commit()
    except Exception:
        session.rollback()
        raise

    refreshed = session.scalar(
        select(Internship)
        .options(
            selectinload(Internship.normalized_title_ref),
            selectinload(Internship.normalized_location_ref),
            selectinload(Internship.skill_requirements).selectinload(
                InternshipSkillRequirement.skill
            ),
        )
        .where(Internship.id == internship.id)
    )
    if refreshed is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Normalized internship was not persisted.",
        )

    return InternshipNormalizationOutcome(
        internship=refreshed,
        normalized_title=refreshed.normalized_title_ref or normalized_title,
        normalized_location=refreshed.normalized_location_ref or normalized_location,
        skill_requirements=refreshed.skill_requirements,
    )
