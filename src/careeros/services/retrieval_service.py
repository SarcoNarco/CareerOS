from __future__ import annotations

import math
from dataclasses import dataclass
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from careeros.db.models.embedding import EmbeddableEntityType, EntityEmbedding
from careeros.db.models.internship import Internship
from careeros.db.models.verification import ApprovedClaim, ClaimStatus
from careeros.services.embedding_provider import EmbeddingProvider
from careeros.services.embedding_service import embed_profile_claims


@dataclass(slots=True)
class CandidateInternship:
    internship: Internship
    similarity_score: float


def retrieve_candidate_internships(
    session: Session,
    profile_id: UUID,
    provider: EmbeddingProvider,
    limit: int = 10,
) -> list[CandidateInternship]:
    embed_profile_claims(session=session, profile_id=profile_id, provider=provider)

    claim_ids = list(
        session.scalars(
            select(ApprovedClaim.id).where(
                ApprovedClaim.profile_id == profile_id,
                ApprovedClaim.status == ClaimStatus.APPROVED,
                ApprovedClaim.retired_at.is_(None),
            )
        )
    )
    claim_embeddings = list(
        session.scalars(
            select(EntityEmbedding).where(
                EntityEmbedding.entity_type == EmbeddableEntityType.APPROVED_CLAIM,
                EntityEmbedding.entity_id.in_(claim_ids),
                EntityEmbedding.embedding_version == provider.embedding_version,
                EntityEmbedding.is_active.is_(True),
            )
        )
    )
    if not claim_embeddings:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active approved claim embeddings found for profile.",
        )

    profile_vector = _average_vectors([embedding.embedding for embedding in claim_embeddings])
    internship_embeddings = list(
        session.scalars(
            select(EntityEmbedding).where(
                EntityEmbedding.entity_type == EmbeddableEntityType.INTERNSHIP,
                EntityEmbedding.embedding_version == provider.embedding_version,
                EntityEmbedding.is_active.is_(True),
            )
        )
    )
    if not internship_embeddings:
        return []

    internship_ids = [embedding.entity_id for embedding in internship_embeddings]
    internships_by_id = {
        internship.id: internship
        for internship in session.scalars(
            select(Internship).where(Internship.id.in_(internship_ids))
        )
    }

    candidates = [
        CandidateInternship(
            internship=internships_by_id[embedding.entity_id],
            similarity_score=_cosine_similarity(profile_vector, embedding.embedding),
        )
        for embedding in internship_embeddings
        if embedding.entity_id in internships_by_id
    ]
    return sorted(candidates, key=lambda candidate: candidate.similarity_score, reverse=True)[:limit]


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
