"""Add lightweight application tracker.

Revision ID: 20260618_0010
Revises: 20260618_0009
Create Date: 2026-06-18 23:59:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260618_0010"
down_revision: str | None = "20260618_0009"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "application_records",
        sa.Column("profile_id", sa.Uuid(), nullable=False),
        sa.Column("internship_id", sa.Uuid(), nullable=False),
        sa.Column("internship_match_id", sa.Uuid(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "saved",
                "applying",
                "applied",
                "interview",
                "rejected",
                "offer",
                "closed",
                "ignored",
                name="application_status",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("priority", sa.SmallInteger(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_action_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["internship_id"], ["internships.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["internship_match_id"],
            ["internship_matches.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(["profile_id"], ["profiles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_application_records_profile_status",
        "application_records",
        ["profile_id", "status"],
        unique=False,
    )
    op.create_index(
        "ix_application_records_profile_priority",
        "application_records",
        ["profile_id", "priority"],
        unique=False,
    )
    op.create_index(
        "ix_application_records_internship_id",
        "application_records",
        ["internship_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_application_records_internship_id", table_name="application_records")
    op.drop_index("ix_application_records_profile_priority", table_name="application_records")
    op.drop_index("ix_application_records_profile_status", table_name="application_records")
    op.drop_table("application_records")
