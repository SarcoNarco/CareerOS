from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from careeros.db.base import utc_now
from careeros.db.models.internship import (
    IngestionRun,
    IngestionRunStatus,
    Internship,
    InternshipStatus,
    RawPosting,
    SourceType,
)
from careeros.schemas.internship import ManualPostingPayload
from careeros.services.deduper import compute_content_hash, compute_dedupe_key, find_duplicate_internship
from careeros.services.normalizer import normalize_posting
from careeros.services.source_registry import get_source


@dataclass(slots=True)
class IngestionOutcome:
    ingestion_run: IngestionRun
    created_internships: list[Internship]
    duplicate_count: int


def ingest_manual_postings(
    session: Session,
    source_id: UUID,
    postings: list[ManualPostingPayload],
) -> IngestionOutcome:
    source = get_source(session=session, source_id=source_id)
    if not source.is_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Internship source is inactive.",
        )
    if source.source_type != SourceType.MANUAL:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only manual sources can be ingested through this endpoint.",
        )

    started_at = utc_now()
    ingestion_run = IngestionRun(
        source_id=source.id,
        started_at=started_at,
        status=IngestionRunStatus.RUNNING,
        items_seen=len(postings),
        items_created=0,
        items_updated=0,
        metadata_json={"adapter": "manual"},
    )
    session.add(ingestion_run)
    session.flush()

    created_internship_ids: list[UUID] = []
    duplicate_count = 0

    try:
        for payload in postings:
            payload_json = payload.model_dump(mode="json")
            content_hash = compute_content_hash(payload_json)
            normalized = normalize_posting(payload)
            dedupe_key = compute_dedupe_key(payload, normalized)

            raw_posting = RawPosting(
                source_id=source.id,
                ingestion_run_id=ingestion_run.id,
                external_id=payload.external_id,
                source_url=str(payload.source_url) if payload.source_url is not None else None,
                payload_json=payload_json,
                content_hash=content_hash,
                fetched_at=utc_now(),
            )
            session.add(raw_posting)
            session.flush()

            duplicate = find_duplicate_internship(
                session=session,
                source_id=source.id,
                dedupe_key=dedupe_key,
                content_hash=content_hash,
            )
            if duplicate is not None:
                duplicate_count += 1
                continue

            internship = Internship(
                source_id=source.id,
                raw_posting_id=raw_posting.id,
                title=normalized.title,
                normalized_title=normalized.normalized_title,
                company_name=payload.company_name.strip(),
                company_domain=payload.company_domain,
                description=payload.description.strip(),
                requirements=payload.requirements,
                responsibilities=payload.responsibilities,
                application_url=str(payload.application_url),
                location_text=normalized.location_text,
                normalized_location=normalized.normalized_location,
                work_mode=normalized.work_mode,
                posted_at=payload.posted_at,
                expires_at=payload.expires_at,
                status=InternshipStatus.ACTIVE,
                dedupe_key=dedupe_key,
                content_hash=content_hash,
            )
            session.add(internship)
            session.flush()
            created_internship_ids.append(internship.id)

        ingestion_run.status = IngestionRunStatus.SUCCEEDED
        ingestion_run.items_created = len(created_internship_ids)
        ingestion_run.items_updated = duplicate_count
        ingestion_run.completed_at = utc_now()
        session.commit()
    except Exception:
        session.rollback()
        raise

    refreshed_run = session.scalar(
        select(IngestionRun)
        .options(selectinload(IngestionRun.raw_postings))
        .where(IngestionRun.id == ingestion_run.id)
    )
    if refreshed_run is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ingestion run was not persisted.",
        )
    created_internships = list(
        session.scalars(
            select(Internship)
            .where(Internship.id.in_(created_internship_ids))
            .order_by(Internship.created_at.asc(), Internship.id.asc())
        )
    )
    return IngestionOutcome(
        ingestion_run=refreshed_run,
        created_internships=created_internships,
        duplicate_count=duplicate_count,
    )
