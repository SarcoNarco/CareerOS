from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from careeros.api.deps import get_db_session, require_api_token
from careeros.schemas.internship import SkillListResponse, SkillResponse
from careeros.services.skill_normalizer import list_skills

router = APIRouter(prefix="/skills", tags=["skills"])


@router.get(
    "",
    response_model=SkillListResponse,
    dependencies=[Depends(require_api_token)],
)
def list_skills_endpoint(
    session: Session = Depends(get_db_session),
) -> SkillListResponse:
    return SkillListResponse(
        items=[SkillResponse.model_validate(skill) for skill in list_skills(session=session)]
    )
