"""Add embeddings and candidate retrieval tables.

Revision ID: 20260618_0006
Revises: 20260618_0005
Create Date: 2026-06-18 23:00:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260618_0006"
down_revision: str | None = "20260618_0005"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "entity_embeddings",
        sa.Column(
            "entity_type",
            sa.Enum(
                "approved_claim",
                "internship",
                name="embeddable_entity_type",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("model_name", sa.String(length=255), nullable=False),
        sa.Column("embedding_version", sa.String(length=255), nullable=False),
        sa.Column("embedding", sa.JSON(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("invalidated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("invalidation_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "embedding_rebuild_queue",
        sa.Column(
            "entity_type",
            sa.Enum(
                "approved_claim",
                "internship",
                name="embeddable_entity_type",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.Column("reason", sa.String(length=255), nullable=False),
        sa.Column("queued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_entity_embeddings_entity_active",
        "entity_embeddings",
        ["entity_type", "entity_id", "is_active"],
        unique=False,
    )
    op.create_index(
        "ix_entity_embeddings_version_active",
        "entity_embeddings",
        ["embedding_version", "is_active"],
        unique=False,
    )
    op.create_index(
        "ix_embedding_rebuild_queue_entity",
        "embedding_rebuild_queue",
        ["entity_type", "entity_id"],
        unique=False,
    )
    op.create_index(
        "ix_embedding_rebuild_queue_unprocessed",
        "embedding_rebuild_queue",
        ["processed_at", "queued_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_embedding_rebuild_queue_unprocessed", table_name="embedding_rebuild_queue")
    op.drop_index("ix_embedding_rebuild_queue_entity", table_name="embedding_rebuild_queue")
    op.drop_index("ix_entity_embeddings_version_active", table_name="entity_embeddings")
    op.drop_index("ix_entity_embeddings_entity_active", table_name="entity_embeddings")
    op.drop_table("embedding_rebuild_queue")
    op.drop_table("entity_embeddings")
