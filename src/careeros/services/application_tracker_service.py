from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from careeros.db.base import utc_now
from careeros.db.models.application import ApplicationRecord, ApplicationStatus
from careeros.db.models.internship import Internship
from careeros.db.models.matching import InternshipMatch
from careeros.db.models.profile import Profile
from careeros.schemas.application import ApplicationCreateRequest, ApplicationUpdateRequest


ARCHIVED_STATUSES = {ApplicationStatus.CLOSED, ApplicationStatus.IGNORED}


@dataclass(slots=True)
class ApplicationSaveResult:
    application: ApplicationRecord
    created: bool


def save_application(
    session: Session,
    payload: ApplicationCreateRequest,
) -> ApplicationSaveResult:
    _validate_profile_exists(session=session, profile_id=payload.profile_id)
    _validate_internship_exists(session=session, internship_id=payload.internship_id)
    if payload.internship_match_id is not None:
        _validate_match_ownership(
            session=session,
            match_id=payload.internship_match_id,
            profile_id=payload.profile_id,
            internship_id=payload.internship_id,
        )

    existing = _find_active_application(
        session=session,
        profile_id=payload.profile_id,
        internship_id=payload.internship_id,
    )
    if existing is not None:
        return ApplicationSaveResult(application=existing, created=False)

    application = ApplicationRecord(
        profile_id=payload.profile_id,
        internship_id=payload.internship_id,
        internship_match_id=payload.internship_match_id,
        status=payload.status,
        priority=payload.priority,
        notes=payload.notes,
        applied_at=payload.applied_at,
        next_action_at=payload.next_action_at,
    )
    _apply_status_defaults(application=application)
    session.add(application)
    session.commit()
    return ApplicationSaveResult(
        application=get_application(session=session, application_id=application.id),
        created=True,
    )


def update_application(
    session: Session,
    application_id: UUID,
    payload: ApplicationUpdateRequest,
) -> ApplicationRecord:
    application = get_application(session=session, application_id=application_id)

    update_fields = payload.model_fields_set
    if "status" in update_fields and payload.status is not None:
        application.status = payload.status
    if "priority" in update_fields and payload.priority is not None:
        application.priority = payload.priority
    if "notes" in update_fields:
        application.notes = payload.notes
    if "applied_at" in update_fields:
        application.applied_at = payload.applied_at
    if "next_action_at" in update_fields:
        application.next_action_at = payload.next_action_at

    _apply_status_defaults(application=application)
    session.commit()
    return get_application(session=session, application_id=application.id)


def archive_application(session: Session, application_id: UUID) -> ApplicationRecord:
    application = get_application(session=session, application_id=application_id)
    application.status = ApplicationStatus.CLOSED
    session.commit()
    return get_application(session=session, application_id=application.id)


def get_application(session: Session, application_id: UUID) -> ApplicationRecord:
    application = session.scalar(
        _application_query().where(ApplicationRecord.id == application_id)
    )
    if application is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application record not found.",
        )
    return application


def list_profile_applications(
    session: Session,
    profile_id: UUID,
    status_filter: ApplicationStatus | None = None,
    priority: int | None = None,
) -> list[ApplicationRecord]:
    _validate_profile_exists(session=session, profile_id=profile_id)
    statement = _application_query().where(ApplicationRecord.profile_id == profile_id)
    if status_filter is not None:
        statement = statement.where(ApplicationRecord.status == status_filter)
    if priority is not None:
        statement = statement.where(ApplicationRecord.priority == priority)
    return list(
        session.scalars(
            statement.order_by(
                ApplicationRecord.priority.asc(),
                ApplicationRecord.next_action_at.asc().nulls_last(),
                ApplicationRecord.updated_at.desc(),
            )
        )
    )


def _application_query():
    return select(ApplicationRecord).options(
        selectinload(ApplicationRecord.internship),
        selectinload(ApplicationRecord.internship_match),
    )


def _find_active_application(
    session: Session,
    profile_id: UUID,
    internship_id: UUID,
) -> ApplicationRecord | None:
    return session.scalar(
        _application_query().where(
            ApplicationRecord.profile_id == profile_id,
            ApplicationRecord.internship_id == internship_id,
            ApplicationRecord.status.not_in(ARCHIVED_STATUSES),
        )
    )


def _validate_profile_exists(session: Session, profile_id: UUID) -> None:
    exists = session.scalar(select(Profile.id).where(Profile.id == profile_id))
    if exists is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found.")


def _validate_internship_exists(session: Session, internship_id: UUID) -> None:
    exists = session.scalar(select(Internship.id).where(Internship.id == internship_id))
    if exists is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Internship not found.")


def _validate_match_ownership(
    session: Session,
    match_id: UUID,
    profile_id: UUID,
    internship_id: UUID,
) -> None:
    match = session.scalar(select(InternshipMatch).where(InternshipMatch.id == match_id))
    if match is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match not found.")
    if match.profile_id != profile_id or match.internship_id != internship_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Match does not belong to the supplied profile and internship.",
        )


def _apply_status_defaults(application: ApplicationRecord) -> None:
    if application.status == ApplicationStatus.APPLIED and application.applied_at is None:
        application.applied_at = utc_now()
