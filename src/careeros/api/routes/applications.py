from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from careeros.api.deps import get_db_session, require_api_token
from careeros.db.models.application import ApplicationRecord, ApplicationStatus
from careeros.schemas.application import (
    ApplicationCreateRequest,
    ApplicationListResponse,
    ApplicationResponse,
    ApplicationUpdateRequest,
)
from careeros.schemas.internship import InternshipResponse
from careeros.schemas.matching import InternshipMatchResponse
from careeros.services.application_tracker_service import (
    archive_application,
    get_application,
    list_profile_applications,
    save_application,
    update_application,
)

router = APIRouter(tags=["applications"])


@router.post(
    "/applications",
    response_model=ApplicationResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_api_token)],
)
def create_application_endpoint(
    payload: ApplicationCreateRequest,
    response: Response,
    session: Session = Depends(get_db_session),
) -> ApplicationResponse:
    result = save_application(session=session, payload=payload)
    if not result.created:
        response.status_code = status.HTTP_200_OK
    return _application_response(result.application)


@router.get(
    "/profiles/{profile_id}/applications",
    response_model=ApplicationListResponse,
    dependencies=[Depends(require_api_token)],
)
def list_profile_applications_endpoint(
    profile_id: UUID,
    status_filter: ApplicationStatus | None = Query(default=None, alias="status"),
    priority: int | None = Query(default=None, ge=1, le=5),
    session: Session = Depends(get_db_session),
) -> ApplicationListResponse:
    applications = list_profile_applications(
        session=session,
        profile_id=profile_id,
        status_filter=status_filter,
        priority=priority,
    )
    return ApplicationListResponse(
        items=[_application_response(application) for application in applications]
    )


@router.get(
    "/applications/{application_id}",
    response_model=ApplicationResponse,
    dependencies=[Depends(require_api_token)],
)
def get_application_endpoint(
    application_id: UUID,
    session: Session = Depends(get_db_session),
) -> ApplicationResponse:
    return _application_response(
        get_application(session=session, application_id=application_id)
    )


@router.patch(
    "/applications/{application_id}",
    response_model=ApplicationResponse,
    dependencies=[Depends(require_api_token)],
)
def update_application_endpoint(
    application_id: UUID,
    payload: ApplicationUpdateRequest,
    session: Session = Depends(get_db_session),
) -> ApplicationResponse:
    application = update_application(
        session=session,
        application_id=application_id,
        payload=payload,
    )
    return _application_response(application)


@router.delete(
    "/applications/{application_id}",
    response_model=ApplicationResponse,
    dependencies=[Depends(require_api_token)],
)
def delete_application_endpoint(
    application_id: UUID,
    session: Session = Depends(get_db_session),
) -> ApplicationResponse:
    return _application_response(
        archive_application(session=session, application_id=application_id)
    )


def _application_response(application: ApplicationRecord) -> ApplicationResponse:
    response = ApplicationResponse.model_validate(application)
    if application.internship is not None:
        response.internship = InternshipResponse.model_validate(application.internship)
    if application.internship_match is not None:
        response.internship_match = InternshipMatchResponse.model_validate(
            application.internship_match
        )
    return response
