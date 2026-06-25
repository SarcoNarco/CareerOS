from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Enum as SqlEnum
from sqlalchemy import ForeignKey, Index, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from careeros.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, enum_values, utc_now

if TYPE_CHECKING:
    pass


class SourceType(str, Enum):
    API = "api"
    RSS = "rss"
    SCRAPER = "scraper"
    MANUAL = "manual"


class SourcePolicyStatus(str, Enum):
    ALLOWED = "allowed"
    REVIEW_NEEDED = "review_needed"
    DISABLED = "disabled"


class IngestionRunStatus(str, Enum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class InternshipStatus(str, Enum):
    ACTIVE = "active"
    CLOSED = "closed"
    EXPIRED = "expired"
    UNKNOWN = "unknown"


class WorkMode(str, Enum):
    ONSITE = "onsite"
    HYBRID = "hybrid"
    REMOTE = "remote"
    UNKNOWN = "unknown"


class InternshipSource(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "internship_sources"

    name: Mapped[str] = mapped_column(String(255), unique=True)
    source_type: Mapped[SourceType] = mapped_column(
        SqlEnum(
            SourceType,
            name="source_type",
            native_enum=False,
            values_callable=enum_values,
            validate_strings=True,
        )
    )
    base_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True)

    policy: Mapped["SourcePolicy | None"] = relationship(
        back_populates="source",
        cascade="all, delete-orphan",
    )
    ingestion_runs: Mapped[list["IngestionRun"]] = relationship(back_populates="source")
    raw_postings: Mapped[list["RawPosting"]] = relationship(back_populates="source")
    internships: Mapped[list["Internship"]] = relationship(back_populates="source")


class SourcePolicy(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "source_policies"

    source_id: Mapped[UUID] = mapped_column(
        ForeignKey("internship_sources.id", ondelete="CASCADE"),
        unique=True,
    )
    policy_status: Mapped[SourcePolicyStatus] = mapped_column(
        SqlEnum(
            SourcePolicyStatus,
            name="source_policy_status",
            native_enum=False,
            values_callable=enum_values,
            validate_strings=True,
        )
    )
    robots_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    terms_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rate_limit_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
    )

    source: Mapped["InternshipSource"] = relationship(back_populates="policy")


class IngestionRun(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "ingestion_runs"

    source_id: Mapped[UUID] = mapped_column(ForeignKey("internship_sources.id", ondelete="CASCADE"))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[IngestionRunStatus] = mapped_column(
        SqlEnum(
            IngestionRunStatus,
            name="ingestion_run_status",
            native_enum=False,
            values_callable=enum_values,
            validate_strings=True,
        )
    )
    items_seen: Mapped[int] = mapped_column(default=0)
    items_created: Mapped[int] = mapped_column(default=0)
    items_updated: Mapped[int] = mapped_column(default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    source: Mapped["InternshipSource"] = relationship(back_populates="ingestion_runs")
    raw_postings: Mapped[list["RawPosting"]] = relationship(back_populates="ingestion_run")


class RawPosting(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "raw_postings"
    __table_args__ = (
        Index("ix_raw_postings_source_content_hash", "source_id", "content_hash"),
        Index("ix_raw_postings_source_url", "source_id", "source_url"),
    )

    source_id: Mapped[UUID] = mapped_column(ForeignKey("internship_sources.id", ondelete="CASCADE"))
    ingestion_run_id: Mapped[UUID] = mapped_column(ForeignKey("ingestion_runs.id", ondelete="CASCADE"))
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    source: Mapped["InternshipSource"] = relationship(back_populates="raw_postings")
    ingestion_run: Mapped["IngestionRun"] = relationship(back_populates="raw_postings")
    internships: Mapped[list["Internship"]] = relationship(back_populates="raw_posting")


class SkillCatalog(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "skill_catalog"

    name: Mapped[str] = mapped_column(String(255), unique=True)
    category: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    aliases: Mapped[list["SkillAlias"]] = relationship(
        back_populates="skill",
        cascade="all, delete-orphan",
    )
    internship_requirements: Mapped[list["InternshipSkillRequirement"]] = relationship(
        back_populates="skill"
    )


class SkillAlias(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "skill_aliases"

    skill_id: Mapped[UUID] = mapped_column(ForeignKey("skill_catalog.id", ondelete="CASCADE"))
    alias: Mapped[str] = mapped_column(String(255), unique=True)
    normalization_source: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    skill: Mapped["SkillCatalog"] = relationship(back_populates="aliases")


class NormalizedTitle(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "normalized_titles"

    canonical_title: Mapped[str] = mapped_column(String(255), unique=True)
    role_family: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    aliases: Mapped[list["TitleAlias"]] = relationship(
        back_populates="normalized_title",
        cascade="all, delete-orphan",
    )
    internships: Mapped[list["Internship"]] = relationship(back_populates="normalized_title_ref")


class TitleAlias(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "title_aliases"

    normalized_title_id: Mapped[UUID] = mapped_column(
        ForeignKey("normalized_titles.id", ondelete="CASCADE")
    )
    alias: Mapped[str] = mapped_column(String(255), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    normalized_title: Mapped["NormalizedTitle"] = relationship(back_populates="aliases")


class NormalizedLocation(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "normalized_locations"

    country: Mapped[str | None] = mapped_column(String(128), nullable=True)
    city: Mapped[str | None] = mapped_column(String(128), nullable=True)
    region: Mapped[str | None] = mapped_column(String(128), nullable=True)
    work_mode: Mapped[WorkMode] = mapped_column(
        SqlEnum(
            WorkMode,
            name="work_mode",
            native_enum=False,
            values_callable=enum_values,
            validate_strings=True,
        )
    )
    canonical_label: Mapped[str] = mapped_column(String(255), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    internships: Mapped[list["Internship"]] = relationship(back_populates="normalized_location_ref")


class Internship(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "internships"
    __table_args__ = (
        UniqueConstraint("source_id", "dedupe_key", name="uq_internships_source_dedupe_key"),
        Index("ix_internships_status_created_at", "status", "created_at"),
        Index("ix_internships_source_content_hash", "source_id", "content_hash"),
    )

    source_id: Mapped[UUID] = mapped_column(ForeignKey("internship_sources.id", ondelete="CASCADE"))
    raw_posting_id: Mapped[UUID] = mapped_column(ForeignKey("raw_postings.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(255))
    normalized_title_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("normalized_titles.id", ondelete="SET NULL"),
        nullable=True,
    )
    normalized_title: Mapped[str] = mapped_column(String(255))
    company_name: Mapped[str] = mapped_column(String(255))
    company_domain: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str] = mapped_column(Text)
    requirements: Mapped[str | None] = mapped_column(Text, nullable=True)
    responsibilities: Mapped[str | None] = mapped_column(Text, nullable=True)
    application_url: Mapped[str] = mapped_column(String(2048))
    location_text: Mapped[str | None] = mapped_column(String(255), nullable=True)
    normalized_location_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("normalized_locations.id", ondelete="SET NULL"),
        nullable=True,
    )
    normalized_location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    work_mode: Mapped[WorkMode] = mapped_column(
        SqlEnum(
            WorkMode,
            name="work_mode",
            native_enum=False,
            values_callable=enum_values,
            validate_strings=True,
        )
    )
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[InternshipStatus] = mapped_column(
        SqlEnum(
            InternshipStatus,
            name="internship_status",
            native_enum=False,
            values_callable=enum_values,
            validate_strings=True,
        )
    )
    dedupe_key: Mapped[str] = mapped_column(String(512))
    content_hash: Mapped[str] = mapped_column(String(64))

    source: Mapped["InternshipSource"] = relationship(back_populates="internships")
    raw_posting: Mapped["RawPosting"] = relationship(back_populates="internships")
    normalized_title_ref: Mapped["NormalizedTitle | None"] = relationship(back_populates="internships")
    normalized_location_ref: Mapped["NormalizedLocation | None"] = relationship(
        back_populates="internships"
    )
    skill_requirements: Mapped[list["InternshipSkillRequirement"]] = relationship(
        back_populates="internship",
        cascade="all, delete-orphan",
    )


class InternshipSkillRequirement(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "internship_skill_requirements"
    __table_args__ = (
        Index("ix_internship_skill_requirements_internship_id", "internship_id"),
        Index("ix_internship_skill_requirements_skill_id", "skill_id"),
    )

    internship_id: Mapped[UUID] = mapped_column(ForeignKey("internships.id", ondelete="CASCADE"))
    skill_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("skill_catalog.id", ondelete="SET NULL"),
        nullable=True,
    )
    skill_name_raw: Mapped[str] = mapped_column(String(255))
    requirement_strength: Mapped[int] = mapped_column()
    is_required: Mapped[bool] = mapped_column(Boolean)
    extraction_method: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    internship: Mapped["Internship"] = relationship(back_populates="skill_requirements")
    skill: Mapped["SkillCatalog | None"] = relationship(back_populates="internship_requirements")
