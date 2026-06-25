from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Enum as SqlEnum, Index, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from careeros.db.base import Base, UUIDPrimaryKeyMixin, enum_values, utc_now


class EmbeddableEntityType(str, Enum):
    APPROVED_CLAIM = "approved_claim"
    INTERNSHIP = "internship"


class EntityEmbedding(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "entity_embeddings"
    __table_args__ = (
        Index(
            "ix_entity_embeddings_entity_active",
            "entity_type",
            "entity_id",
            "is_active",
        ),
        Index(
            "ix_entity_embeddings_version_active",
            "embedding_version",
            "is_active",
        ),
    )

    entity_type: Mapped[EmbeddableEntityType] = mapped_column(
        SqlEnum(
            EmbeddableEntityType,
            name="embeddable_entity_type",
            native_enum=False,
            values_callable=enum_values,
            validate_strings=True,
        )
    )
    entity_id: Mapped[UUID] = mapped_column()
    content_hash: Mapped[str] = mapped_column(String(64))
    model_name: Mapped[str] = mapped_column(String(255))
    embedding_version: Mapped[str] = mapped_column(String(255))
    embedding: Mapped[list[float]] = mapped_column(JSON)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    invalidated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    invalidation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class EmbeddingRebuildQueue(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "embedding_rebuild_queue"
    __table_args__ = (
        Index("ix_embedding_rebuild_queue_unprocessed", "processed_at", "queued_at"),
        Index("ix_embedding_rebuild_queue_entity", "entity_type", "entity_id"),
    )

    entity_type: Mapped[EmbeddableEntityType] = mapped_column(
        SqlEnum(
            EmbeddableEntityType,
            name="embeddable_entity_type",
            native_enum=False,
            values_callable=enum_values,
            validate_strings=True,
        )
    )
    entity_id: Mapped[UUID] = mapped_column()
    reason: Mapped[str] = mapped_column(String(255))
    queued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
