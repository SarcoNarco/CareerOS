from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from careeros.api.deps import get_db_session, require_api_token
from careeros.db.models.internship import Internship
from careeros.schemas.internship import InternshipListResponse, InternshipResponse

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
