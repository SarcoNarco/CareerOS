"""Add truthful resume generation tables.

Revision ID: 20260618_0009
Revises: 20260618_0008
Create Date: 2026-06-18 23:55:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260618_0009"
down_revision: str | None = "20260618_0008"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "resume_templates",
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("template_engine", sa.String(length=64), nullable=False),
        sa.Column("template_path", sa.String(length=1024), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_table(
        "generated_resumes",
        sa.Column("profile_id", sa.Uuid(), nullable=False),
        sa.Column("internship_id", sa.Uuid(), nullable=True),
        sa.Column("template_id", sa.Uuid(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("draft", "approved", "exported", name="resume_status", native_enum=False),
            nullable=False,
        ),
        sa.Column("rendered_html_path", sa.Text(), nullable=True),
        sa.Column("rendered_pdf_path", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["internship_id"], ["internships.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["profile_id"], ["profiles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["template_id"], ["resume_templates.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "generated_resume_claims",
        sa.Column("generated_resume_id", sa.Uuid(), nullable=False),
        sa.Column("approved_claim_id", sa.Uuid(), nullable=False),
        sa.Column("section_name", sa.String(length=128), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.Column("rendered_text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["approved_claim_id"],
            ["approved_claims.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["generated_resume_id"],
            ["generated_resumes.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_generated_resumes_profile_created_at",
        "generated_resumes",
        ["profile_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_generated_resume_claims_resume_order",
        "generated_resume_claims",
        ["generated_resume_id", "display_order"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_generated_resume_claims_resume_order", table_name="generated_resume_claims")
    op.drop_index("ix_generated_resumes_profile_created_at", table_name="generated_resumes")
    op.drop_table("generated_resume_claims")
    op.drop_table("generated_resumes")
    op.drop_table("resume_templates")
