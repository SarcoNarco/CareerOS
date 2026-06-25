from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from careeros.api.deps import get_db_session, require_api_token
from careeros.db.models.internship import Internship
from careeros.schemas.internship import (
    InternshipListResponse,
    InternshipNormalizeResponse,
    InternshipResponse,
    InternshipSkillRequirementListResponse,
    InternshipSkillRequirementResponse,
    NormalizedLocationResponse,
    NormalizedTitleResponse,
)
from careeros.services.internship_normalization_service import normalize_internship
from careeros.services.skill_extractor import list_internship_skill_requirements

router = APIRouter(prefix="/internships", tags=["internships"])


@router.get(
    "",
    response_model=InternshipListResponse,
    dependencies=[Depends(require_api_token)],
)
def list_internships_endpoint(
    session: Session = Depends(get_db_session),
) -> InternshipListResponse:
    internships = list(
        session.scalars(
            select(Internship).order_by(Internship.created_at.desc(), Internship.id.asc())
        )
    )
    return InternshipListResponse(
        items=[InternshipResponse.model_validate(internship) for internship in internships]
    )


@router.get(
    "/{internship_id}",
    response_model=InternshipResponse,
    dependencies=[Depends(require_api_token)],
)
def get_internship_endpoint(
    internship_id: UUID,
    session: Session = Depends(get_db_session),
) -> InternshipResponse:
    internship = session.scalar(select(Internship).where(Internship.id == internship_id))
    if internship is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Internship not found.",
        )
    return InternshipResponse.model_validate(internship)


@router.post(
    "/{internship_id}/normalize",
    response_model=InternshipNormalizeResponse,
    dependencies=[Depends(require_api_token)],
)
def normalize_internship_endpoint(
    internship_id: UUID,
    session: Session = Depends(get_db_session),
) -> InternshipNormalizeResponse:
    outcome = normalize_internship(session=session, internship_id=internship_id)
    return InternshipNormalizeResponse(
        internship=InternshipResponse.model_validate(outcome.internship),
        normalized_title=NormalizedTitleResponse.model_validate(outcome.normalized_title),
        normalized_location=NormalizedLocationResponse.model_validate(outcome.normalized_location),
        skill_requirements=[
            InternshipSkillRequirementResponse.model_validate(requirement)
            for requirement in outcome.skill_requirements
        ],
    )


@router.get(
    "/{internship_id}/skills",
    response_model=InternshipSkillRequirementListResponse,
    dependencies=[Depends(require_api_token)],
)
def list_internship_skill_requirements_endpoint(
    internship_id: UUID,
    session: Session = Depends(get_db_session),
) -> InternshipSkillRequirementListResponse:
    internship, requirements = list_internship_skill_requirements(
        session=session,
        internship_id=internship_id,
    )
    return InternshipSkillRequirementListResponse(
        internship_id=internship.id,
        items=[
            InternshipSkillRequirementResponse.model_validate(requirement)
            for requirement in requirements
        ],
    )
