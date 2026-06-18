"""Add approved claims and verification events.

Revision ID: 20260618_0003
Revises: 20260613_0002
Create Date: 2026-06-18 20:30:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260618_0003"
down_revision: str | None = "20260613_0002"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "approved_claims",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("profile_id", sa.Uuid(), nullable=False),
        sa.Column("owning_entity_type", sa.String(length=64), nullable=False),
        sa.Column("owning_entity_id", sa.Uuid(), nullable=True),
        sa.Column("claim_text", sa.Text(), nullable=False),
        sa.Column("claim_type", sa.String(length=64), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "approved",
                "rejected",
                "retired",
                name="claim_status",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("source_document_id", sa.Uuid(), nullable=False),
        sa.Column("source_primary_span_id", sa.Uuid(), nullable=True),
        sa.Column("approved_from_candidate_id", sa.Uuid(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["approved_from_candidate_id"], ["fact_candidates.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["profile_id"], ["profiles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_document_id"], ["source_documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_primary_span_id"], ["fact_evidence_spans.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "verification_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("fact_candidate_id", sa.Uuid(), nullable=True),
        sa.Column("approved_claim_id", sa.Uuid(), nullable=True),
        sa.Column("actor_user_id", sa.Uuid(), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["approved_claim_id"], ["approved_claims.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["fact_candidate_id"], ["fact_candidates.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_approved_claims_profile_status",
        "approved_claims",
        ["profile_id", "status"],
        unique=False,
    )
    op.create_index(
        "ix_approved_claims_approved_from_candidate_id",
        "approved_claims",
        ["approved_from_candidate_id"],
        unique=False,
    )
    op.create_index(
        "ix_verification_events_fact_candidate_id",
        "verification_events",
        ["fact_candidate_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_verification_events_fact_candidate_id", table_name="verification_events")
    op.drop_index("ix_approved_claims_approved_from_candidate_id", table_name="approved_claims")
    op.drop_index("ix_approved_claims_profile_status", table_name="approved_claims")
    op.drop_table("verification_events")
    op.drop_table("approved_claims")
