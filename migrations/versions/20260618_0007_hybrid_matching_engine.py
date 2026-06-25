"""Add hybrid matching tables.

Revision ID: 20260618_0007
Revises: 20260618_0006
Create Date: 2026-06-18 23:30:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260618_0007"
down_revision: str | None = "20260618_0006"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "match_runs",
        sa.Column("profile_id", sa.Uuid(), nullable=False),
        sa.Column("scoring_version", sa.String(length=255), nullable=False),
        sa.Column("embedding_version", sa.String(length=255), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["profile_id"], ["profiles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "internship_matches",
        sa.Column("match_run_id", sa.Uuid(), nullable=False),
        sa.Column("profile_id", sa.Uuid(), nullable=False),
        sa.Column("internship_id", sa.Uuid(), nullable=False),
        sa.Column("total_score", sa.Numeric(5, 2), nullable=False),
        sa.Column("hard_filter_passed", sa.Boolean(), nullable=False),
        sa.Column("normalized_feature_score", sa.Numeric(5, 2), nullable=False),
        sa.Column("semantic_score", sa.Numeric(5, 2), nullable=False),
        sa.Column("skill_score", sa.Numeric(5, 2), nullable=False),
        sa.Column("experience_score", sa.Numeric(5, 2), nullable=False),
        sa.Column("preference_score", sa.Numeric(5, 2), nullable=False),
        sa.Column("gap_penalty", sa.Numeric(5, 2), nullable=False),
        sa.Column("explanation_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["internship_id"], ["internships.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["match_run_id"], ["match_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["profile_id"], ["profiles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_match_runs_profile_started_at",
        "match_runs",
        ["profile_id", "started_at"],
        unique=False,
    )
    op.create_index(
        "ix_internship_matches_match_run_score",
        "internship_matches",
        ["match_run_id", "total_score"],
        unique=False,
    )
    op.create_index(
        "ix_internship_matches_profile_total_score",
        "internship_matches",
        ["profile_id", "total_score"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_internship_matches_profile_total_score", table_name="internship_matches")
    op.drop_index("ix_internship_matches_match_run_score", table_name="internship_matches")
    op.drop_index("ix_match_runs_profile_started_at", table_name="match_runs")
    op.drop_table("internship_matches")
    op.drop_table("match_runs")
