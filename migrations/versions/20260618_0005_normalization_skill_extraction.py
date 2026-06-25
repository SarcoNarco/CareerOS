"""Add normalization and skill extraction tables.

Revision ID: 20260618_0005
Revises: 20260618_0004
Create Date: 2026-06-18 22:00:00
"""

from collections.abc import Sequence
from datetime import datetime, timezone
from uuid import UUID

from alembic import op
import sqlalchemy as sa


revision: str = "20260618_0005"
down_revision: str | None = "20260618_0004"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "skill_catalog",
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_table(
        "normalized_titles",
        sa.Column("canonical_title", sa.String(length=255), nullable=False),
        sa.Column("role_family", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("canonical_title"),
    )
    op.create_table(
        "normalized_locations",
        sa.Column("country", sa.String(length=128), nullable=True),
        sa.Column("city", sa.String(length=128), nullable=True),
        sa.Column("region", sa.String(length=128), nullable=True),
        sa.Column(
            "work_mode",
            sa.Enum("onsite", "hybrid", "remote", "unknown", name="work_mode", native_enum=False),
            nullable=False,
        ),
        sa.Column("canonical_label", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("canonical_label"),
    )
    op.create_table(
        "skill_aliases",
        sa.Column("skill_id", sa.Uuid(), nullable=False),
        sa.Column("alias", sa.String(length=255), nullable=False),
        sa.Column("normalization_source", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["skill_id"], ["skill_catalog.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("alias"),
    )
    op.create_table(
        "title_aliases",
        sa.Column("normalized_title_id", sa.Uuid(), nullable=False),
        sa.Column("alias", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["normalized_title_id"], ["normalized_titles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("alias"),
    )
    with op.batch_alter_table("internships") as batch_op:
        batch_op.add_column(sa.Column("normalized_title_id", sa.Uuid(), nullable=True))
        batch_op.add_column(sa.Column("normalized_location_id", sa.Uuid(), nullable=True))
        batch_op.create_foreign_key(
            "fk_internships_normalized_title_id",
            "normalized_titles",
            ["normalized_title_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_foreign_key(
            "fk_internships_normalized_location_id",
            "normalized_locations",
            ["normalized_location_id"],
            ["id"],
            ondelete="SET NULL",
        )
    op.create_table(
        "internship_skill_requirements",
        sa.Column("internship_id", sa.Uuid(), nullable=False),
        sa.Column("skill_id", sa.Uuid(), nullable=True),
        sa.Column("skill_name_raw", sa.String(length=255), nullable=False),
        sa.Column("requirement_strength", sa.Integer(), nullable=False),
        sa.Column("is_required", sa.Boolean(), nullable=False),
        sa.Column("extraction_method", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["internship_id"], ["internships.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["skill_id"], ["skill_catalog.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_internship_skill_requirements_internship_id",
        "internship_skill_requirements",
        ["internship_id"],
        unique=False,
    )
    op.create_index(
        "ix_internship_skill_requirements_skill_id",
        "internship_skill_requirements",
        ["skill_id"],
        unique=False,
    )

    _seed_normalization_data()


def downgrade() -> None:
    op.drop_index("ix_internship_skill_requirements_skill_id", table_name="internship_skill_requirements")
    op.drop_index("ix_internship_skill_requirements_internship_id", table_name="internship_skill_requirements")
    op.drop_table("internship_skill_requirements")
    with op.batch_alter_table("internships") as batch_op:
        batch_op.drop_constraint("fk_internships_normalized_location_id", type_="foreignkey")
        batch_op.drop_constraint("fk_internships_normalized_title_id", type_="foreignkey")
        batch_op.drop_column("normalized_location_id")
        batch_op.drop_column("normalized_title_id")
    op.drop_table("title_aliases")
    op.drop_table("skill_aliases")
    op.drop_table("normalized_locations")
    op.drop_table("normalized_titles")
    op.drop_table("skill_catalog")


def _seed_normalization_data() -> None:
    now = datetime.now(timezone.utc)

    skill_catalog = sa.table(
        "skill_catalog",
        sa.column("id", sa.Uuid()),
        sa.column("name", sa.String()),
        sa.column("category", sa.String()),
        sa.column("created_at", sa.DateTime(timezone=True)),
    )
    skill_aliases = sa.table(
        "skill_aliases",
        sa.column("id", sa.Uuid()),
        sa.column("skill_id", sa.Uuid()),
        sa.column("alias", sa.String()),
        sa.column("normalization_source", sa.String()),
        sa.column("created_at", sa.DateTime(timezone=True)),
    )
    normalized_titles = sa.table(
        "normalized_titles",
        sa.column("id", sa.Uuid()),
        sa.column("canonical_title", sa.String()),
        sa.column("role_family", sa.String()),
        sa.column("created_at", sa.DateTime(timezone=True)),
    )
    title_aliases = sa.table(
        "title_aliases",
        sa.column("id", sa.Uuid()),
        sa.column("normalized_title_id", sa.Uuid()),
        sa.column("alias", sa.String()),
        sa.column("created_at", sa.DateTime(timezone=True)),
    )
    normalized_locations = sa.table(
        "normalized_locations",
        sa.column("id", sa.Uuid()),
        sa.column("country", sa.String()),
        sa.column("city", sa.String()),
        sa.column("region", sa.String()),
        sa.column("work_mode", sa.String()),
        sa.column("canonical_label", sa.String()),
        sa.column("created_at", sa.DateTime(timezone=True)),
    )

    skills = [
        ("00000000-0000-4000-8000-000000000001", "Python", "programming_language", ["python", "py"]),
        ("00000000-0000-4000-8000-000000000002", "SQL", "database", ["sql"]),
        ("00000000-0000-4000-8000-000000000003", "PostgreSQL", "database", ["postgresql", "postgres", "psql"]),
        ("00000000-0000-4000-8000-000000000004", "Machine Learning", "ai_ml", ["machine learning", "ml"]),
        ("00000000-0000-4000-8000-000000000005", "Deep Learning", "ai_ml", ["deep learning", "dl"]),
        ("00000000-0000-4000-8000-000000000006", "PyTorch", "ai_ml", ["pytorch", "torch"]),
        ("00000000-0000-4000-8000-000000000007", "TensorFlow", "ai_ml", ["tensorflow", "tf"]),
        ("00000000-0000-4000-8000-000000000008", "scikit-learn", "ai_ml", ["scikit-learn", "sklearn", "scikit learn"]),
        ("00000000-0000-4000-8000-000000000009", "Pandas", "data", ["pandas"]),
        ("00000000-0000-4000-8000-000000000010", "NumPy", "data", ["numpy", "np"]),
        ("00000000-0000-4000-8000-000000000011", "FastAPI", "backend", ["fastapi"]),
        ("00000000-0000-4000-8000-000000000012", "Docker", "devops", ["docker", "containerization"]),
        ("00000000-0000-4000-8000-000000000013", "Git", "tooling", ["git", "github"]),
        ("00000000-0000-4000-8000-000000000014", "JavaScript", "programming_language", ["javascript", "js"]),
        ("00000000-0000-4000-8000-000000000015", "React", "frontend", ["react", "react.js", "reactjs"]),
    ]
    op.bulk_insert(
        skill_catalog,
        [
            {"id": UUID(skill_id), "name": name, "category": category, "created_at": now}
            for skill_id, name, category, _ in skills
        ],
    )
    alias_rows = []
    alias_counter = 1
    for skill_id, _, _, aliases in skills:
        for alias in aliases:
            alias_rows.append(
                {
                    "id": UUID(f"00000000-0000-4001-8000-{alias_counter:012d}"),
                    "skill_id": UUID(skill_id),
                    "alias": alias,
                    "normalization_source": "manual",
                    "created_at": now,
                }
            )
            alias_counter += 1
    op.bulk_insert(skill_aliases, alias_rows)

    titles = [
        ("00000000-0000-4002-8000-000000000001", "ML", "ml", ["machine learning intern", "ml intern", "ai intern", "ml engineer intern", "machine learning internship"]),
        ("00000000-0000-4002-8000-000000000002", "Data", "data", ["data analyst intern", "data science intern", "data intern", "data scientist intern"]),
        ("00000000-0000-4002-8000-000000000003", "SWE", "swe", ["software engineer intern", "software engineering intern", "backend intern", "software developer intern", "sde intern"]),
        ("00000000-0000-4002-8000-000000000004", "Other", "other", ["intern"]),
    ]
    op.bulk_insert(
        normalized_titles,
        [
            {"id": UUID(title_id), "canonical_title": title, "role_family": family, "created_at": now}
            for title_id, title, family, _ in titles
        ],
    )
    title_alias_rows = []
    alias_counter = 1
    for title_id, _, _, aliases in titles:
        for alias in aliases:
            title_alias_rows.append(
                {
                    "id": UUID(f"00000000-0000-4003-8000-{alias_counter:012d}"),
                    "normalized_title_id": UUID(title_id),
                    "alias": alias,
                    "created_at": now,
                }
            )
            alias_counter += 1
    op.bulk_insert(title_aliases, title_alias_rows)

    op.bulk_insert(
        normalized_locations,
        [
            {
                "id": UUID("00000000-0000-4004-8000-000000000001"),
                "country": None,
                "city": None,
                "region": None,
                "work_mode": "remote",
                "canonical_label": "Remote",
                "created_at": now,
            },
            {
                "id": UUID("00000000-0000-4004-8000-000000000002"),
                "country": None,
                "city": None,
                "region": None,
                "work_mode": "hybrid",
                "canonical_label": "Hybrid",
                "created_at": now,
            },
            {
                "id": UUID("00000000-0000-4004-8000-000000000003"),
                "country": None,
                "city": None,
                "region": None,
                "work_mode": "onsite",
                "canonical_label": "Onsite",
                "created_at": now,
            },
            {
                "id": UUID("00000000-0000-4004-8000-000000000004"),
                "country": None,
                "city": None,
                "region": None,
                "work_mode": "unknown",
                "canonical_label": "Unknown",
                "created_at": now,
            },
        ],
    )
