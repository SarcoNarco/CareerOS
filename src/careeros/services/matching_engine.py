from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from careeros.db.base import utc_now
from careeros.db.models.embedding import EmbeddableEntityType, EntityEmbedding
from careeros.db.models.fact_staging import ExtractionStatus
from careeros.db.models.internship import InternshipStatus
from careeros.db.models.matching import InternshipMatch, MatchRun
from careeros.services.embedding_provider import EmbeddingProvider
from careeros.services.embedding_service import embed_internship, embed_profile_claims
from careeros.services.feature_builder import (
    InternshipFeatures,
    ProfileFeatures,
    build_all_internship_features,
    build_profile_features,
)
from careeros.services.score_explainer import build_score_explanation


@dataclass(slots=True)
class MatchComputation:
    match_run: MatchRun
    matches: list[InternshipMatch]


def recompute_matches(
    session: Session,
    profile_id: UUID,
    provider: EmbeddingProvider,
    scoring_version: str,
    limit: int | None = None,
    internship_ids: set[UUID] | None = None,
) -> MatchComputation:
    profile_features = build_profile_features(session=session, profile_id=profile_id)
    internship_features = build_all_internship_features(
        session=session,
        internship_ids=internship_ids,
    )
    if not internship_features:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No internships found to match.",
        )

    # Embeddings are maintained before the match transaction so they keep their own lifecycle.
    embed_profile_claims(session=session, profile_id=profile_id, provider=provider)
    for item in internship_features:
        embed_internship(session=session, internship_id=item.internship.id, provider=provider)

    timestamp = utc_now()
    match_run = MatchRun(
        profile_id=profile_id,
        scoring_version=scoring_version,
        embedding_version=provider.embedding_version,
        started_at=timestamp,
        status=ExtractionStatus.RUNNING,
    )
    session.add(match_run)
    session.flush()

    try:
        scored_matches = [
            _score_internship(
                session=session,
                match_run=match_run,
                profile_features=profile_features,
                internship_features=item,
                provider=provider,
                scoring_version=scoring_version,
            )
            for item in internship_features
        ]
        scored_matches.sort(key=lambda match: float(match.total_score), reverse=True)
        if limit is not None:
            scored_matches = scored_matches[:limit]

        for match in scored_matches:
            session.add(match)

        match_run.status = ExtractionStatus.SUCCEEDED
        match_run.completed_at = utc_now()
        session.commit()
    except Exception:
        match_run.status = ExtractionStatus.FAILED
        match_run.completed_at = utc_now()
        session.rollback()
        raise

    return MatchComputation(match_run=match_run, matches=scored_matches)


def list_matches(
    session: Session,
    profile_id: UUID | None = None,
    limit: int = 100,
) -> list[InternshipMatch]:
    statement = select(InternshipMatch)
    if profile_id is not None:
        statement = statement.where(InternshipMatch.profile_id == profile_id)
    return list(
        session.scalars(
            statement.order_by(InternshipMatch.total_score.desc(), InternshipMatch.created_at.desc()).limit(limit)
        )
    )


def get_match(session: Session, match_id: UUID) -> InternshipMatch:
    match = session.scalar(select(InternshipMatch).where(InternshipMatch.id == match_id))
    if match is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Match not found.",
        )
    return match


def get_top_matches(
    session: Session,
    profile_id: UUID,
    limit: int = 10,
) -> list[InternshipMatch]:
    return list_matches(session=session, profile_id=profile_id, limit=limit)


def _score_internship(
    session: Session,
    match_run: MatchRun,
    profile_features: ProfileFeatures,
    internship_features: InternshipFeatures,
    provider: EmbeddingProvider,
    scoring_version: str,
) -> InternshipMatch:
    hard_filter_passed = internship_features.internship.status in {
        InternshipStatus.ACTIVE,
        InternshipStatus.UNKNOWN,
    }
    normalized_feature_score = _normalized_feature_score(
        profile_features=profile_features,
        internship_features=internship_features,
    )
    semantic_score = _semantic_score(
        session=session,
        profile_features=profile_features,
        internship_features=internship_features,
        provider=provider,
    )
    skill_score = _skill_score(
        profile_features=profile_features,
        internship_features=internship_features,
    )
    experience_score = _experience_score(
        profile_features=profile_features,
        internship_features=internship_features,
    )
    preference_score = normalized_feature_score
    gap_penalty = 0.0

    weighted = (
        0.40 * normalized_feature_score
        + 0.25 * semantic_score
        + 0.20 * skill_score
        + 0.15 * experience_score
    )
    total_score = weighted if hard_filter_passed else 0.0
    total_score = max(0.0, total_score - gap_penalty)

    score_payload = {
        "hard_filter_passed": 1.0 if hard_filter_passed else 0.0,
        "normalized_feature_score": normalized_feature_score,
        "semantic_score": semantic_score,
        "skill_score": skill_score,
        "experience_score": experience_score,
        "preference_score": preference_score,
        "gap_penalty": gap_penalty,
        "total_score": total_score,
    }
    explanation = build_score_explanation(
        profile_features=profile_features,
        internship_features=internship_features,
        scores=score_payload,
    )
    explanation["scoring_version"] = scoring_version

    return InternshipMatch(
        match_run_id=match_run.id,
        profile_id=profile_features.profile_id,
        internship_id=internship_features.internship.id,
        total_score=_decimal_score(total_score),
        hard_filter_passed=hard_filter_passed,
        normalized_feature_score=_decimal_score(normalized_feature_score),
        semantic_score=_decimal_score(semantic_score),
        skill_score=_decimal_score(skill_score),
        experience_score=_decimal_score(experience_score),
        preference_score=_decimal_score(preference_score),
        gap_penalty=_decimal_score(gap_penalty),
        explanation_json=explanation,
        created_at=utc_now(),
    )


def _normalized_feature_score(
    profile_features: ProfileFeatures,
    internship_features: InternshipFeatures,
) -> float:
    role_score = _role_score(profile_features=profile_features, internship_features=internship_features)
    location_score = _location_score(profile_features=profile_features, internship_features=internship_features)
    return _clamp_score(0.65 * role_score + 0.35 * location_score)


def _role_score(profile_features: ProfileFeatures, internship_features: InternshipFeatures) -> float:
    if not profile_features.target_roles:
        return 50.0
    haystack = " ".join(
        part
        for part in (
            internship_features.normalized_title,
            internship_features.role_family,
            internship_features.internship.title.casefold(),
        )
        if part
    )
    for role in profile_features.target_roles:
        if role in haystack:
            return 100.0
        if "backend" in role and ("swe" in haystack or "software" in haystack):
            return 90.0
        if "software" in role and "swe" in haystack:
            return 90.0
        if "machine learning" in role and "ml" in haystack:
            return 95.0
        if role == "ml intern" and "ml" in haystack:
            return 95.0
        if "data" in role and "data" in haystack:
            return 95.0
    return 20.0


def _location_score(profile_features: ProfileFeatures, internship_features: InternshipFeatures) -> float:
    if not profile_features.target_locations:
        return 50.0
    haystack = " ".join(
        part
        for part in (
            internship_features.normalized_location,
            internship_features.work_mode.value,
            internship_features.internship.location_text.casefold()
            if internship_features.internship.location_text
            else None,
        )
        if part
    )
    for location in profile_features.target_locations:
        if location in haystack:
            return 100.0
    return 25.0


def _semantic_score(
    session: Session,
    profile_features: ProfileFeatures,
    internship_features: InternshipFeatures,
    provider: EmbeddingProvider,
) -> float:
    claim_embeddings = list(
        session.scalars(
            select(EntityEmbedding).where(
                EntityEmbedding.entity_type == EmbeddableEntityType.APPROVED_CLAIM,
                EntityEmbedding.entity_id.in_([claim.id for claim in profile_features.approved_claims]),
                EntityEmbedding.embedding_version == provider.embedding_version,
                EntityEmbedding.is_active.is_(True),
            )
        )
    )
    internship_embedding = session.scalar(
        select(EntityEmbedding).where(
            EntityEmbedding.entity_type == EmbeddableEntityType.INTERNSHIP,
            EntityEmbedding.entity_id == internship_features.internship.id,
            EntityEmbedding.embedding_version == provider.embedding_version,
            EntityEmbedding.is_active.is_(True),
        )
    )
    if not claim_embeddings or internship_embedding is None:
        return 0.0
    profile_vector = _average_vectors([embedding.embedding for embedding in claim_embeddings])
    return _clamp_score(max(0.0, _cosine_similarity(profile_vector, internship_embedding.embedding)) * 100.0)


def _skill_score(profile_features: ProfileFeatures, internship_features: InternshipFeatures) -> float:
    if not profile_features.skill_names or not internship_features.skill_names:
        return 0.0
    overlap = profile_features.skill_names & internship_features.skill_names
    denominator = len(profile_features.skill_names) + len(internship_features.skill_names)
    return _clamp_score((2 * len(overlap) / denominator) * 100.0)


def _experience_score(profile_features: ProfileFeatures, internship_features: InternshipFeatures) -> float:
    if not profile_features.tokens or not internship_features.tokens:
        return 0.0
    overlap = profile_features.tokens & internship_features.tokens
    denominator = min(len(profile_features.tokens), len(internship_features.tokens))
    if denominator == 0:
        return 0.0
    return _clamp_score((len(overlap) / denominator) * 100.0)


def _average_vectors(vectors: list[list[float]]) -> list[float]:
    if not vectors:
        return []
    dimension = len(vectors[0])
    averaged = [
        sum(vector[index] for vector in vectors) / len(vectors)
        for index in range(dimension)
    ]
    return _normalize(averaged)


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return sum(a * b for a, b in zip(left, right, strict=True)) / (left_norm * right_norm)


def _normalize(values: list[float]) -> list[float]:
    norm = math.sqrt(sum(value * value for value in values))
    if norm == 0:
        return values
    return [value / norm for value in values]


def _clamp_score(value: float) -> float:
    return max(0.0, min(100.0, value))


def _decimal_score(value: float) -> Decimal:
    return Decimal(str(_clamp_score(value))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
