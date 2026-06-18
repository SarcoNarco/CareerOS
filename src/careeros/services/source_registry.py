from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from careeros.db.models.internship import InternshipSource, SourcePolicy
from careeros.schemas.internship import SourceCreateRequest


def list_sources(session: Session) -> list[InternshipSource]:
    return list(
        session.scalars(
            select(InternshipSource)
            .options(selectinload(InternshipSource.policy))
            .order_by(InternshipSource.created_at.asc(), InternshipSource.id.asc())
        )
    )


def get_source(session: Session, source_id: UUID) -> InternshipSource:
    source = session.scalar(
        select(InternshipSource)
        .options(selectinload(InternshipSource.policy))
        .where(InternshipSource.id == source_id)
    )
    if source is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Internship source not found.",
        )
    return source


def create_source(session: Session, payload: SourceCreateRequest) -> InternshipSource:
    source = InternshipSource(
        name=payload.name.strip(),
        source_type=payload.source_type,
        base_url=str(payload.base_url) if payload.base_url is not None else None,
        is_active=payload.is_active,
    )
    policy = SourcePolicy(
        source=source,
        policy_status=payload.policy_status,
        notes=payload.policy_notes,
    )
    session.add_all([source, policy])

    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Internship source already exists.",
        ) from exc

    return get_source(session=session, source_id=source.id)
