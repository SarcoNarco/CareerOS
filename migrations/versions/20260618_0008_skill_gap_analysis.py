"""Add skill gap analysis table.

Revision ID: 20260618_0008
Revises: 20260618_0007
Create Date: 2026-06-18 23:45:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260618_0008"
down_revision: str | None = "20260618_0007"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "skill_gap_items",
        sa.Column("internship_match_id", sa.Uuid(), nullable=False),
        sa.Column("skill_id", sa.Uuid(), nullable=True),
        sa.Column("skill_name_raw", sa.String(length=255), nullable=False),
        sa.Column("severity", sa.SmallInteger(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("recommendation", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["internship_match_id"],
            ["internship_matches.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["skill_id"], ["skill_catalog.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "internship_match_id",
            "skill_id",
            "skill_name_raw",
            name="uq_skill_gap_items_match_skill",
        ),
    )
    op.create_index(
        "ix_skill_gap_items_match_id",
        "skill_gap_items",
        ["internship_match_id"],
        unique=False,
    )
    op.create_index(
        "ix_skill_gap_items_skill_id",
        "skill_gap_items",
        ["skill_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_skill_gap_items_skill_id", table_name="skill_gap_items")
    op.drop_index("ix_skill_gap_items_match_id", table_name="skill_gap_items")
    op.drop_table("skill_gap_items")
