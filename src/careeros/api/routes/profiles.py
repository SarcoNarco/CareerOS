from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from careeros.api.deps import get_db_session, require_api_token
from careeros.schemas.profile import ProfileCreateRequest, ProfileResponse
from careeros.services.profile_service import create_profile, get_profile

router = APIRouter(prefix="/profiles", tags=["profiles"])


@router.post(
    "",
    response_model=ProfileResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_api_token)],
)
def create_profile_endpoint(
    payload: ProfileCreateRequest,
    session: Session = Depends(get_db_session),
) -> ProfileResponse:
    profile = create_profile(session=session, payload=payload)
    return ProfileResponse.model_validate(profile)


@router.get(
    "/{profile_id}",
    response_model=ProfileResponse,
    dependencies=[Depends(require_api_token)],
)
def get_profile_endpoint(
    profile_id: UUID,
    session: Session = Depends(get_db_session),
) -> ProfileResponse:
    profile = get_profile(session=session, profile_id=profile_id)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found.",
        )
    return ProfileResponse.model_validate(profile)

