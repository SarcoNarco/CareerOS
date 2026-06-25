from __future__ import annotations

import hashlib
from dataclasses import dataclass
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from careeros.db.base import utc_now
from careeros.db.models.embedding import (
    EmbeddableEntityType,
    EmbeddingRebuildQueue,
    EntityEmbedding,
)
from careeros.db.models.internship import Internship, InternshipSkillRequirement
from careeros.db.models.verification import ApprovedClaim, ClaimStatus
from careeros.services.embedding_provider import EmbeddingProvider


@dataclass(slots=True)
class EmbeddingResult:
    embedding: EntityEmbedding
    created: bool


@dataclass(slots=True)
class RebuildResult:
    queued_count: int
    processed_count: int
    created_count: int


def embed_approved_claim(
    session: Session,
    claim_id: UUID,
    provider: EmbeddingProvider,
) -> EmbeddingResult:
    try:
        result = _embed_entity(
            session=session,
            entity_type=EmbeddableEntityType.APPROVED_CLAIM,
            entity_id=claim_id,
            provider=provider,
        )
        session.commit()
        return result
    except Exception:
        session.rollback()
        raise


def embed_internship(
    session: Session,
    internship_id: UUID,
    provider: EmbeddingProvider,
) -> EmbeddingResult:
    try:
        result = _embed_entity(
            session=session,
            entity_type=EmbeddableEntityType.INTERNSHIP,
            entity_id=internship_id,
            provider=provider,
        )
        session.commit()
        return result
    except Exception:
        session.rollback()
        raise


def embed_profile_claims(
    session: Session,
    profile_id: UUID,
    provider: EmbeddingProvider,
) -> list[EmbeddingResult]:
    claims = _get_approved_claims_for_profile(session=session, profile_id=profile_id)
    try:
        results = [
            _embed_entity(
                session=session,
                entity_type=EmbeddableEntityType.APPROVED_CLAIM,
                entity_id=claim.id,
                provider=provider,
            )
            for claim in claims
        ]
        session.commit()
        return results
    except Exception:
        session.rollback()
        raise


def invalidate_entity_embeddings(
    session: Session,
    entity_type: EmbeddableEntityType,
    entity_id: UUID,
    reason: str,
    queue_rebuild: bool = True,
) -> int:
    active_embeddings = _get_active_embeddings(
        session=session,
        entity_type=entity_type,
        entity_id=entity_id,
    )
    timestamp = utc_now()
    for embedding in active_embeddings:
        embedding.is_active = False
        embedding.invalidated_at = timestamp
        embedding.invalidation_reason = reason

    if queue_rebuild:
        session.add(
            EmbeddingRebuildQueue(
                entity_type=entity_type,
                entity_id=entity_id,
                reason=reason,
                queued_at=timestamp,
                metadata_json={},
            )
        )
    session.flush()
    return len(active_embeddings)


def queue_all_rebuilds(session: Session, reason: str = "manual_rebuild") -> int:
    queued_count = 0
    timestamp = utc_now()
    for claim in _get_all_approved_claims(session=session):
        session.add(
            EmbeddingRebuildQueue(
                entity_type=EmbeddableEntityType.APPROVED_CLAIM,
                entity_id=claim.id,
                reason=reason,
                queued_at=timestamp,
                metadata_json={},
            )
        )
        queued_count += 1
    for internship in _get_all_active_internships(session=session):
        session.add(
            EmbeddingRebuildQueue(
                entity_type=EmbeddableEntityType.INTERNSHIP,
                entity_id=internship.id,
                reason=reason,
                queued_at=timestamp,
                metadata_json={},
            )
        )
        queued_count += 1
    session.flush()
    return queued_count


def process_rebuild_queue(
    session: Session,
    provider: EmbeddingProvider,
    limit: int = 100,
) -> RebuildResult:
    queue_items = list(
        session.scalars(
            select(EmbeddingRebuildQueue)
            .where(EmbeddingRebuildQueue.processed_at.is_(None))
            .order_by(EmbeddingRebuildQueue.queued_at.asc(), EmbeddingRebuildQueue.id.asc())
            .limit(limit)
        )
    )
    created_count = 0
    timestamp = utc_now()
    try:
        for item in queue_items:
            result = _embed_entity(
                session=session,
                entity_type=item.entity_type,
                entity_id=item.entity_id,
                provider=provider,
            )
            if result.created:
                created_count += 1
            item.processed_at = timestamp
        session.commit()
    except Exception:
        session.rollback()
        raise
    return RebuildResult(
        queued_count=0,
        processed_count=len(queue_items),
        created_count=created_count,
    )


def rebuild_all_embeddings(
    session: Session,
    provider: EmbeddingProvider,
    limit: int = 100,
) -> RebuildResult:
    try:
        queued_count = queue_all_rebuilds(session=session)
        session.flush()
        result = process_rebuild_queue(session=session, provider=provider, limit=limit)
        return RebuildResult(
            queued_count=queued_count,
            processed_count=result.processed_count,
            created_count=result.created_count,
        )
    except Exception:
        session.rollback()
        raise


def get_active_embedding(
    session: Session,
    entity_type: EmbeddableEntityType,
    entity_id: UUID,
    embedding_version: str,
) -> EntityEmbedding | None:
    return session.scalar(
        select(EntityEmbedding).where(
            EntityEmbedding.entity_type == entity_type,
            EntityEmbedding.entity_id == entity_id,
            EntityEmbedding.embedding_version == embedding_version,
            EntityEmbedding.is_active.is_(True),
        )
    )


def build_claim_embedding_text(claim: ApprovedClaim) -> str:
    return claim.claim_text.strip()


def build_internship_embedding_text(internship: Internship) -> str:
    skill_names = []
    for requirement in internship.skill_requirements:
        if requirement.skill is not None:
            skill_names.append(requirement.skill.name)
        else:
            skill_names.append(requirement.skill_name_raw)

    return "\n".join(
        part
        for part in (
            internship.title,
            internship.normalized_title,
            internship.company_name,
            internship.location_text,
            internship.normalized_location,
            internship.description,
            internship.requirements,
            internship.responsibilities,
            " ".join(sorted(set(skill_names))),
        )
        if part
    ).strip()


def content_hash_for_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _embed_entity(
    session: Session,
    entity_type: EmbeddableEntityType,
    entity_id: UUID,
    provider: EmbeddingProvider,
) -> EmbeddingResult:
    text = _get_embedding_text(session=session, entity_type=entity_type, entity_id=entity_id)
    content_hash = content_hash_for_text(text)

    active_embeddings = _get_active_embeddings(
        session=session,
        entity_type=entity_type,
        entity_id=entity_id,
    )
    for embedding in active_embeddings:
        if (
            embedding.content_hash == content_hash
            and embedding.model_name == provider.model_name
            and embedding.embedding_version == provider.embedding_version
        ):
            return EmbeddingResult(embedding=embedding, created=False)

    if active_embeddings:
        reason = "embedding_version_changed"
        if any(embedding.content_hash != content_hash for embedding in active_embeddings):
            reason = "content_changed"
        invalidate_entity_embeddings(
            session=session,
            entity_type=entity_type,
            entity_id=entity_id,
            reason=reason,
            queue_rebuild=False,
        )

    new_embedding = EntityEmbedding(
        entity_type=entity_type,
        entity_id=entity_id,
        content_hash=content_hash,
        model_name=provider.model_name,
        embedding_version=provider.embedding_version,
        embedding=provider.embed_text(text),
        is_active=True,
        invalidated_at=None,
        invalidation_reason=None,
        created_at=utc_now(),
    )
    session.add(new_embedding)
    session.flush()
    return EmbeddingResult(embedding=new_embedding, created=True)


def _get_embedding_text(
    session: Session,
    entity_type: EmbeddableEntityType,
    entity_id: UUID,
) -> str:
    if entity_type == EmbeddableEntityType.APPROVED_CLAIM:
        claim = session.scalar(
            select(ApprovedClaim).where(
                ApprovedClaim.id == entity_id,
                ApprovedClaim.status == ClaimStatus.APPROVED,
            )
        )
        if claim is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Approved claim not found.",
            )
        return build_claim_embedding_text(claim)

    internship = session.scalar(
        select(Internship)
        .options(
            selectinload(Internship.skill_requirements).selectinload(
                InternshipSkillRequirement.skill
            )
        )
        .where(Internship.id == entity_id)
    )
    if internship is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Internship not found.",
        )
    return build_internship_embedding_text(internship)


def _get_active_embeddings(
    session: Session,
    entity_type: EmbeddableEntityType,
    entity_id: UUID,
) -> list[EntityEmbedding]:
    return list(
        session.scalars(
            select(EntityEmbedding).where(
                EntityEmbedding.entity_type == entity_type,
                EntityEmbedding.entity_id == entity_id,
                EntityEmbedding.is_active.is_(True),
            )
        )
    )


def _get_approved_claims_for_profile(session: Session, profile_id: UUID) -> list[ApprovedClaim]:
    claims = list(
        session.scalars(
            select(ApprovedClaim)
            .where(
                ApprovedClaim.profile_id == profile_id,
                ApprovedClaim.status == ClaimStatus.APPROVED,
                ApprovedClaim.retired_at.is_(None),
            )
            .order_by(ApprovedClaim.created_at.asc(), ApprovedClaim.id.asc())
        )
    )
    if not claims:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No approved claims found for profile.",
        )
    return claims


def _get_all_approved_claims(session: Session) -> list[ApprovedClaim]:
    return list(
        session.scalars(
            select(ApprovedClaim).where(
                ApprovedClaim.status == ClaimStatus.APPROVED,
                ApprovedClaim.retired_at.is_(None),
            )
        )
    )


def _get_all_active_internships(session: Session) -> list[Internship]:
    return list(session.scalars(select(Internship)))
