from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from careeros.db.base import utc_now
from careeros.db.models.fact_staging import (
    CandidateKind,
    ExtractionRun,
    ExtractionStatus,
    FactCandidate,
    FactEvidenceSpan,
    VerificationStatus,
)
from careeros.db.models.profile import Profile
from careeros.db.models.source_document import SourceDocument
from careeros.schemas.extraction import ExtractionSummaryResponse
from careeros.services.candidate_generator import CandidateSeed, generate_candidates
from careeros.services.document_extractor import extract_text_from_path


@dataclass(slots=True)
class PersistedCandidate:
    key: str
    candidate: FactCandidate


def extract_document_candidates(session: Session, document_id: UUID) -> ExtractionSummaryResponse:
    document = session.scalar(
        select(SourceDocument).where(SourceDocument.id == document_id)
    )
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source document not found.",
        )

    profile = session.scalar(select(Profile).where(Profile.user_id == document.user_id))
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found for source document.",
        )

    extracted_text = _ensure_extracted_text(session=session, document=document)
    started_at = utc_now()
    extraction_run = ExtractionRun(
        source_document_id=document.id,
        status=ExtractionStatus.RUNNING,
        model_name=None,
        prompt_version="deterministic-rules-v1",
        input_sha256=hashlib.sha256(extracted_text.encode("utf-8")).hexdigest(),
        output_json=None,
        error_message=None,
        started_at=started_at,
        completed_at=None,
    )
    session.add(extraction_run)
    session.flush()

    try:
        seeds = generate_candidates(extracted_text)
        persisted = _persist_candidates(
            session=session,
            extraction_run=extraction_run,
            profile_id=profile.id,
            source_document_id=document.id,
            seeds=seeds,
        )
    except Exception as exc:
        extraction_run.status = ExtractionStatus.FAILED
        extraction_run.error_message = str(exc)
        extraction_run.completed_at = utc_now()
        session.commit()
        raise

    counts_by_kind: dict[str, int] = {}
    evidence_span_count = 0
    for item in persisted:
        key = item.candidate.candidate_kind.value
        counts_by_kind[key] = counts_by_kind.get(key, 0) + 1
        evidence_span_count += len(item.candidate.evidence_spans)

    extraction_run.status = ExtractionStatus.SUCCEEDED
    extraction_run.completed_at = utc_now()
    extraction_run.output_json = {
        "candidate_count": len(persisted),
        "evidence_span_count": evidence_span_count,
        "candidates_by_kind": counts_by_kind,
    }
    session.commit()
    session.refresh(extraction_run)

    return ExtractionSummaryResponse(
        extraction_run_id=extraction_run.id,
        source_document_id=document.id,
        status=extraction_run.status,
        extracted_text_length=len(extracted_text),
        candidate_count=len(persisted),
        evidence_span_count=evidence_span_count,
        candidates_by_kind=counts_by_kind,
        started_at=extraction_run.started_at,
        completed_at=extraction_run.completed_at,
    )


def _ensure_extracted_text(session: Session, document: SourceDocument) -> str:
    if document.extracted_text:
        return document.extracted_text

    storage_path = Path(document.storage_path)
    extracted_text = extract_text_from_path(storage_path)
    document.extracted_text = extracted_text
    session.flush()
    return extracted_text


def _persist_candidates(
    *,
    session: Session,
    extraction_run: ExtractionRun,
    profile_id: UUID,
    source_document_id: UUID,
    seeds: list[CandidateSeed],
) -> list[PersistedCandidate]:
    persisted: list[PersistedCandidate] = []
    parent_lookup: dict[str, FactCandidate] = {}

    ordered_seeds = sorted(seeds, key=_candidate_sort_key)
    for index, seed in enumerate(ordered_seeds):
        parent_candidate = parent_lookup.get(seed.parent_key) if seed.parent_key else None
        candidate = FactCandidate(
            extraction_run_id=extraction_run.id,
            profile_id=profile_id,
            candidate_kind=seed.candidate_kind,
            parent_candidate_id=parent_candidate.id if parent_candidate else None,
            structured_data=seed.structured_data,
            status=VerificationStatus.PENDING,
            reviewer_notes=None,
            created_at=utc_now(),
            reviewed_at=None,
        )
        session.add(candidate)
        session.flush()

        for span in seed.evidence_spans:
            evidence = FactEvidenceSpan(
                source_document_id=source_document_id,
                fact_candidate_id=candidate.id,
                source_text_start=span.start,
                source_text_end=span.end,
                snippet_text=span.text,
                confidence_score=None,
                created_at=utc_now(),
            )
            session.add(evidence)

        if seed.parent_key and seed.candidate_kind == CandidateKind.PROJECT:
            parent_lookup[seed.parent_key] = candidate
        elif seed.parent_key and parent_candidate is None:
            parent_lookup[f"orphan:{index}"] = candidate

        persisted.append(PersistedCandidate(key=f"candidate:{index}", candidate=candidate))

    session.flush()
    return persisted


def _candidate_sort_key(seed: CandidateSeed) -> tuple[int, int]:
    priority = {
        CandidateKind.EDUCATION: 0,
        CandidateKind.PROJECT: 1,
        CandidateKind.SKILL: 2,
        CandidateKind.CLAIM: 3,
    }
    first_start = seed.evidence_spans[0].start if seed.evidence_spans else 0
    return (priority.get(seed.candidate_kind, 99), first_start)
