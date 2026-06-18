"""Add internship ingestion foundation.

Revision ID: 20260618_0004
Revises: 20260618_0003
Create Date: 2026-06-18 21:15:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260618_0004"
down_revision: str | None = "20260618_0003"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "internship_sources",
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column(
            "source_type",
            sa.Enum("api", "rss", "scraper", "manual", name="source_type", native_enum=False),
            nullable=False,
        ),
        sa.Column("base_url", sa.String(length=1024), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_table(
        "source_policies",
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column(
            "policy_status",
            sa.Enum(
                "allowed",
                "review_needed",
                "disabled",
                name="source_policy_status",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("robots_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("terms_reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rate_limit_notes", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["source_id"], ["internship_sources.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_id"),
    )
    op.create_table(
        "ingestion_runs",
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "running",
                "succeeded",
                "failed",
                name="ingestion_run_status",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("items_seen", sa.Integer(), nullable=False),
        sa.Column("items_created", sa.Integer(), nullable=False),
        sa.Column("items_updated", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["source_id"], ["internship_sources.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "raw_postings",
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("ingestion_run_id", sa.Uuid(), nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=True),
        sa.Column("source_url", sa.String(length=2048), nullable=True),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["ingestion_run_id"], ["ingestion_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_id"], ["internship_sources.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "internships",
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("raw_posting_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("normalized_title", sa.String(length=255), nullable=False),
        sa.Column("company_name", sa.String(length=255), nullable=False),
        sa.Column("company_domain", sa.String(length=255), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("requirements", sa.Text(), nullable=True),
        sa.Column("responsibilities", sa.Text(), nullable=True),
        sa.Column("application_url", sa.String(length=2048), nullable=False),
        sa.Column("location_text", sa.String(length=255), nullable=True),
        sa.Column("normalized_location", sa.String(length=255), nullable=True),
        sa.Column(
            "work_mode",
            sa.Enum("onsite", "hybrid", "remote", "unknown", name="work_mode", native_enum=False),
            nullable=False,
        ),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "status",
            sa.Enum("active", "closed", "expired", "unknown", name="internship_status", native_enum=False),
            nullable=False,
        ),
        sa.Column("dedupe_key", sa.String(length=512), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["raw_posting_id"], ["raw_postings.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_id"], ["internship_sources.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_id", "dedupe_key", name="uq_internships_source_dedupe_key"),
    )
    op.create_index("ix_raw_postings_content_hash", "raw_postings", ["content_hash"], unique=False)
    op.create_index("ix_raw_postings_source_content_hash", "raw_postings", ["source_id", "content_hash"], unique=False)
    op.create_index("ix_raw_postings_source_url", "raw_postings", ["source_id", "source_url"], unique=False)
    op.create_index("ix_internships_status_created_at", "internships", ["status", "created_at"], unique=False)
    op.create_index("ix_internships_source_content_hash", "internships", ["source_id", "content_hash"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_internships_source_content_hash", table_name="internships")
    op.drop_index("ix_internships_status_created_at", table_name="internships")
    op.drop_index("ix_raw_postings_source_url", table_name="raw_postings")
    op.drop_index("ix_raw_postings_source_content_hash", table_name="raw_postings")
    op.drop_index("ix_raw_postings_content_hash", table_name="raw_postings")
    op.drop_table("internships")
    op.drop_table("raw_postings")
    op.drop_table("ingestion_runs")
    op.drop_table("source_policies")
    op.drop_table("internship_sources")
