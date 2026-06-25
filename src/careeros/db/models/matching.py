from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Enum as SqlEnum, ForeignKey, Index, JSON, Numeric, SmallInteger, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from careeros.db.base import Base, UUIDPrimaryKeyMixin, enum_values
from careeros.db.models.fact_staging import ExtractionStatus
from careeros.db.models.internship import SkillCatalog


class MatchRun(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "match_runs"
    __table_args__ = (
        Index("ix_match_runs_profile_started_at", "profile_id", "started_at"),
    )

    profile_id: Mapped[UUID] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"))
    scoring_version: Mapped[str] = mapped_column(String(255))
    embedding_version: Mapped[str] = mapped_column(String(255))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[ExtractionStatus] = mapped_column(
        SqlEnum(
            ExtractionStatus,
            name="extraction_status",
            native_enum=False,
            values_callable=enum_values,
            validate_strings=True,
        )
    )

    matches: Mapped[list["InternshipMatch"]] = relationship(
        back_populates="match_run",
        cascade="all, delete-orphan",
    )


class InternshipMatch(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "internship_matches"
    __table_args__ = (
        Index("ix_internship_matches_profile_total_score", "profile_id", "total_score"),
        Index("ix_internship_matches_match_run_score", "match_run_id", "total_score"),
    )

    match_run_id: Mapped[UUID] = mapped_column(ForeignKey("match_runs.id", ondelete="CASCADE"))
    profile_id: Mapped[UUID] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"))
    internship_id: Mapped[UUID] = mapped_column(ForeignKey("internships.id", ondelete="CASCADE"))
    total_score: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    hard_filter_passed: Mapped[bool] = mapped_column(Boolean)
    normalized_feature_score: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    semantic_score: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    skill_score: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    experience_score: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    preference_score: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    gap_penalty: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    explanation_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    match_run: Mapped["MatchRun"] = relationship(back_populates="matches")
    skill_gap_items: Mapped[list["SkillGapItem"]] = relationship(
        back_populates="internship_match",
        cascade="all, delete-orphan",
    )


class SkillGapItem(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "skill_gap_items"
    __table_args__ = (
        UniqueConstraint(
            "internship_match_id",
            "skill_id",
            "skill_name_raw",
            name="uq_skill_gap_items_match_skill",
        ),
        Index("ix_skill_gap_items_match_id", "internship_match_id"),
        Index("ix_skill_gap_items_skill_id", "skill_id"),
    )

    internship_match_id: Mapped[UUID] = mapped_column(
        ForeignKey("internship_matches.id", ondelete="CASCADE")
    )
    skill_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("skill_catalog.id", ondelete="SET NULL"),
        nullable=True,
    )
    skill_name_raw: Mapped[str] = mapped_column(String(255))
    severity: Mapped[int] = mapped_column(SmallInteger)
    reason: Mapped[str] = mapped_column(Text)
    recommendation: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    internship_match: Mapped["InternshipMatch"] = relationship(back_populates="skill_gap_items")
    skill: Mapped["SkillCatalog | None"] = relationship()
