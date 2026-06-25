from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from careeros.core.config import Settings
from careeros.db.models.internship import (
    Internship,
    InternshipSkillRequirement,
    WorkMode,
)
from careeros.db.models.matching import InternshipMatch, MatchRun
from careeros.services.embedding_provider import EmbeddingProvider
from careeros.services.embedding_service import (
    EmbeddingResult,
    embed_internship,
    embed_profile_claims,
)
from careeros.services.gap_analysis_service import MatchGapAnalysis, analyze_match_gaps
from careeros.services.internship_normalization_service import normalize_internship
from careeros.services.matching_engine import recompute_matches
from careeros.services.source_adapters import FetchJson, sync_source_adapter

DiscoveryScope = Literal["latest-run", "source", "all"]


@dataclass(slots=True)
class DiscoveryResult:
    rank: int
    match: InternshipMatch
    internship: Internship
    matched_skills: list[str]
    missing_skills: list[str]


@dataclass(slots=True)
class JobDiscoveryOutcome:
    source_name: str
    scope: DiscoveryScope
    ingestion_run_id: UUID
    items_seen: int
    items_created: int
    duplicate_count: int
    internships_considered: int
    polluted_by_other_sources: bool
    normalized_count: int
    internship_embeddings_created: int
    profile_embeddings_created: int
    match_run: MatchRun
    results: list[DiscoveryResult]


def run_job_discovery(
    *,
    session: Session,
    profile_id: UUID,
    source_name: str,
    limit: int,
    min_score: Decimal | None,
    remote_only: bool,
    role_family: str | None,
    provider: EmbeddingProvider,
    settings: Settings,
    top_matches: int = 10,
    scope: DiscoveryScope = "latest-run",
    fetch_json: FetchJson | None = None,
) -> JobDiscoveryOutcome:
    ingestion = sync_source_adapter(
        session=session,
        source_name=source_name,
        limit=limit,
        fetch_json=fetch_json,
    )

    scoped_internship_ids = _internship_ids_for_scope(
        session=session,
        source_id=ingestion.ingestion_run.source_id,
        created_internships=ingestion.created_internships,
        scope=scope,
    )

    normalized_count = 0
    internship_embeddings: list[EmbeddingResult] = []
    for internship in _load_internships_for_normalization(
        session=session,
        internship_ids=scoped_internship_ids,
    ):
        normalize_internship(session=session, internship_id=internship.id)
        normalized_count += 1
        internship_embeddings.append(
            embed_internship(
                session=session,
                internship_id=internship.id,
                provider=provider,
            )
        )

    profile_embeddings = embed_profile_claims(
        session=session,
        profile_id=profile_id,
        provider=provider,
    )
    match_computation = recompute_matches(
        session=session,
        profile_id=profile_id,
        provider=provider,
        scoring_version=settings.scoring_version,
        internship_ids=scoped_internship_ids if scope != "all" else None,
    )

    results: list[DiscoveryResult] = []
    rank = 1
    for match in match_computation.matches:
        internship = _load_internship(session=session, internship_id=match.internship_id)
        if not _passes_filters(
            match=match,
            internship=internship,
            min_score=min_score,
            remote_only=remote_only,
            role_family=role_family,
        ):
            continue
        gaps = analyze_match_gaps(session=session, match_id=match.id)
        results.append(
            DiscoveryResult(
                rank=rank,
                match=match,
                internship=internship,
                matched_skills=_matched_skills(match),
                missing_skills=_missing_skills(gaps),
            )
        )
        rank += 1
        if len(results) >= top_matches:
            break

    return JobDiscoveryOutcome(
        source_name=source_name,
        scope=scope,
        ingestion_run_id=ingestion.ingestion_run.id,
        items_seen=ingestion.ingestion_run.items_seen,
        items_created=ingestion.ingestion_run.items_created,
        duplicate_count=ingestion.duplicate_count,
        internships_considered=len(scoped_internship_ids),
        polluted_by_other_sources=any(
            result.internship.source_id != ingestion.ingestion_run.source_id
            for result in results
        ),
        normalized_count=normalized_count,
        internship_embeddings_created=sum(1 for result in internship_embeddings if result.created),
        profile_embeddings_created=sum(1 for result in profile_embeddings if result.created),
        match_run=match_computation.match_run,
        results=results,
    )


def _internship_ids_for_scope(
    *,
    session: Session,
    source_id: UUID,
    created_internships: list[Internship],
    scope: DiscoveryScope,
) -> set[UUID]:
    if scope == "all":
        return set(session.scalars(select(Internship.id)))
    if scope == "latest-run" and created_internships:
        return {internship.id for internship in created_internships}
    return set(
        session.scalars(
            select(Internship.id)
            .where(Internship.source_id == source_id)
            .order_by(Internship.created_at.desc(), Internship.id.asc())
        )
    )


def _load_internships_for_normalization(
    *,
    session: Session,
    internship_ids: set[UUID],
) -> list[Internship]:
    if not internship_ids:
        return []
    return list(
        session.scalars(
            select(Internship)
            .options(selectinload(Internship.skill_requirements))
            .where(Internship.id.in_(internship_ids))
            .order_by(Internship.created_at.asc(), Internship.id.asc())
        )
    )


def _load_internship(session: Session, internship_id: UUID) -> Internship:
    internship = session.scalar(
        select(Internship)
        .options(
            selectinload(Internship.normalized_title_ref),
            selectinload(Internship.normalized_location_ref),
            selectinload(Internship.skill_requirements).selectinload(
                InternshipSkillRequirement.skill
            ),
        )
        .where(Internship.id == internship_id)
    )
    if internship is None:
        raise RuntimeError(f"Internship not found after matching: {internship_id}")
    return internship


def _passes_filters(
    *,
    match: InternshipMatch,
    internship: Internship,
    min_score: Decimal | None,
    remote_only: bool,
    role_family: str | None,
) -> bool:
    if min_score is not None and match.total_score < min_score:
        return False
    if remote_only and internship.work_mode != WorkMode.REMOTE:
        return False
    if role_family is not None:
        actual_role_family = (
            internship.normalized_title_ref.role_family
            if internship.normalized_title_ref is not None
            else None
        )
        if actual_role_family != role_family:
            return False
    return True


def _matched_skills(match: InternshipMatch) -> list[str]:
    signals = match.explanation_json.get("signals", {})
    matched = signals.get("matched_skills", []) if isinstance(signals, dict) else []
    if not isinstance(matched, list):
        return []
    return [str(skill) for skill in matched]


def _missing_skills(gaps: MatchGapAnalysis) -> list[str]:
    return [
        gap.skill.name if gap.skill is not None else gap.skill_name_raw
        for gap in gaps.missing_skills
    ]
