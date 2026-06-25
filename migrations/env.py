from __future__ import annotations

from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

from careeros.core.config import get_settings
from careeros.db.base import Base
from careeros.db.models.embedding import EmbeddingRebuildQueue, EntityEmbedding  # noqa: F401
from careeros.db.models.fact_staging import (  # noqa: F401
    ExtractionRun,
    FactCandidate,
    FactEvidenceSpan,
)
from careeros.db.models.internship import (  # noqa: F401
    IngestionRun,
    Internship,
    InternshipSkillRequirement,
    InternshipSource,
    NormalizedLocation,
    NormalizedTitle,
    RawPosting,
    SkillAlias,
    SkillCatalog,
    SourcePolicy,
    TitleAlias,
)
from careeros.db.models.matching import InternshipMatch, MatchRun, SkillGapItem  # noqa: F401
from careeros.db.models.profile import Profile  # noqa: F401
from careeros.db.models.resume import GeneratedResume, GeneratedResumeClaim, ResumeTemplate  # noqa: F401
from careeros.db.models.source_document import SourceDocument  # noqa: F401
from careeros.db.models.user import User  # noqa: F401
from careeros.db.models.verification import ApprovedClaim, VerificationEvent  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

settings = get_settings()
database_url = settings.database_url
if "@db:5432" in database_url and not Path("/.dockerenv").exists():
    database_url = database_url.replace("@db:5432", "@127.0.0.1:5432")
config.set_main_option("sqlalchemy.url", database_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section, {})
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
