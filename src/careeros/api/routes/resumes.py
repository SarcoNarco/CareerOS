from uuid import UUID

from fastapi import APIRouter, Depends, status
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from careeros.api.deps import get_db_session, get_settings, require_api_token
from careeros.core.config import Settings
from careeros.schemas.resume import (
    GeneratedResumeClaimListResponse,
    GeneratedResumeClaimResponse,
    GeneratedResumeDetailResponse,
    GeneratedResumeResponse,
    ResumeGenerateRequest,
)
from careeros.services.resume_assembler import (
    generate_resume,
    get_generated_resume,
    list_generated_resume_claims,
)

router = APIRouter(prefix="/resumes", tags=["resumes"])


@router.post(
    "/generate",
    response_model=GeneratedResumeDetailResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_api_token)],
)
def generate_resume_endpoint(
    payload: ResumeGenerateRequest,
    session: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> GeneratedResumeDetailResponse:
    result = generate_resume(
        session=session,
        profile_id=payload.profile_id,
        internship_id=payload.internship_id,
        template_id=payload.template_id,
        storage_root=settings.storage_root,
        max_claims=payload.max_claims,
    )
    return _detail_response(result)


@router.get(
    "/{resume_id}",
    response_model=GeneratedResumeDetailResponse,
    dependencies=[Depends(require_api_token)],
)
def get_resume_endpoint(
    resume_id: UUID,
    session: Session = Depends(get_db_session),
) -> GeneratedResumeDetailResponse:
    result = get_generated_resume(session=session, resume_id=resume_id)
    return _detail_response(result)


@router.get(
    "/{resume_id}/claims",
    response_model=GeneratedResumeClaimListResponse,
    dependencies=[Depends(require_api_token)],
)
def get_resume_claims_endpoint(
    resume_id: UUID,
    session: Session = Depends(get_db_session),
) -> GeneratedResumeClaimListResponse:
    claims = list_generated_resume_claims(session=session, resume_id=resume_id)
    return GeneratedResumeClaimListResponse(
        resume_id=resume_id,
        items=[
            GeneratedResumeClaimResponse.model_validate(claim)
            for claim in claims
        ],
    )


@router.get(
    "/{resume_id}/html",
    response_class=HTMLResponse,
    dependencies=[Depends(require_api_token)],
)
def get_resume_html_endpoint(
    resume_id: UUID,
    session: Session = Depends(get_db_session),
) -> HTMLResponse:
    result = get_generated_resume(session=session, resume_id=resume_id)
    path = result.resume.rendered_html_path
    if path is None:
        return HTMLResponse("<p>No rendered HTML artifact is available.</p>", status_code=404)
    try:
        html = open(path, encoding="utf-8").read()
    except FileNotFoundError:
        return HTMLResponse("<p>Rendered HTML artifact was not found.</p>", status_code=404)
    return HTMLResponse(html)


def _detail_response(result) -> GeneratedResumeDetailResponse:
    return GeneratedResumeDetailResponse(
        resume=GeneratedResumeResponse.model_validate(result.resume),
        claims=[
            GeneratedResumeClaimResponse.model_validate(claim)
            for claim in result.claim_links
        ],
    )
