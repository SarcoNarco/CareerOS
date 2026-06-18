"""Add fact staging pipeline tables.

Revision ID: 20260613_0002
Revises: 20260613_0001
Create Date: 2026-06-13 23:30:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260613_0002"
down_revision: str | None = "20260613_0001"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "extraction_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_document_id", sa.Uuid(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "queued",
                "running",
                "succeeded",
                "failed",
                name="extraction_status",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("model_name", sa.String(length=255), nullable=True),
        sa.Column("prompt_version", sa.String(length=255), nullable=True),
        sa.Column("input_sha256", sa.String(length=64), nullable=False),
        sa.Column("output_json", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["source_document_id"], ["source_documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "fact_candidates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("extraction_run_id", sa.Uuid(), nullable=False),
        sa.Column("profile_id", sa.Uuid(), nullable=False),
        sa.Column(
            "candidate_kind",
            sa.Enum(
                "education",
                "experience",
                "project",
                "skill",
                "certification",
                "link",
                "claim",
                name="candidate_kind",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("parent_candidate_id", sa.Uuid(), nullable=True),
        sa.Column("structured_data", sa.JSON(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "approved",
                "rejected",
                "edited",
                name="verification_status",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("reviewer_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["extraction_run_id"], ["extraction_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parent_candidate_id"], ["fact_candidates.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["profile_id"], ["profiles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "fact_evidence_spans",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_document_id", sa.Uuid(), nullable=False),
        sa.Column("fact_candidate_id", sa.Uuid(), nullable=True),
        sa.Column("source_text_start", sa.Integer(), nullable=False),
        sa.Column("source_text_end", sa.Integer(), nullable=False),
        sa.Column("snippet_text", sa.Text(), nullable=False),
        sa.Column("confidence_score", sa.Numeric(5, 2), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["fact_candidate_id"], ["fact_candidates.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_document_id"], ["source_documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_fact_candidates_profile_status_kind",
        "fact_candidates",
        ["profile_id", "status", "candidate_kind"],
        unique=False,
    )
    op.create_index(
        "ix_fact_evidence_spans_source_document_id",
        "fact_evidence_spans",
        ["source_document_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_fact_evidence_spans_source_document_id", table_name="fact_evidence_spans")
    op.drop_index("ix_fact_candidates_profile_status_kind", table_name="fact_candidates")
    op.drop_table("fact_evidence_spans")
    op.drop_table("fact_candidates")
    op.drop_table("extraction_runs")
