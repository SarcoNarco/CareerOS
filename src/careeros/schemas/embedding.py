from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from careeros.db.models.embedding import EmbeddableEntityType
from careeros.schemas.internship import InternshipResponse


class EntityEmbeddingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    entity_type: EmbeddableEntityType
    entity_id: UUID
    content_hash: str
    model_name: str
    embedding_version: str
    is_active: bool
    invalidated_at: datetime | None
    invalidation_reason: str | None
    created_at: datetime


class EmbedEntityResponse(BaseModel):
    embedding: EntityEmbeddingResponse
    created: bool


class EmbedProfileResponse(BaseModel):
    profile_id: UUID
    embeddings: list[EmbedEntityResponse]


class RebuildEmbeddingsRequest(BaseModel):
    process: bool = True
    limit: int = Field(default=100, ge=1, le=1000)


class RebuildEmbeddingsResponse(BaseModel):
    queued_count: int
    processed_count: int
    created_count: int


class EmbeddingRebuildQueueResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    entity_type: EmbeddableEntityType
    entity_id: UUID
    reason: str
    queued_at: datetime
    processed_at: datetime | None
    metadata_json: dict[str, Any]


class CandidateInternshipResponse(BaseModel):
    internship: InternshipResponse
    similarity_score: float


class CandidateInternshipListResponse(BaseModel):
    profile_id: UUID
    items: list[CandidateInternshipResponse]
