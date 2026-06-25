from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import DateTime, Enum as SqlEnum
from sqlalchemy import ForeignKey, JSON, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from careeros.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, enum_values

if TYPE_CHECKING:
    from careeros.db.models.profile import Profile
    from careeros.db.models.source_document import SourceDocument
    from careeros.db.models.verification import ApprovedClaim, VerificationEvent


class ExtractionStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class CandidateKind(str, Enum):
    EDUCATION = "education"
    EXPERIENCE = "experience"
    PROJECT = "project"
    SKILL = "skill"
    CERTIFICATION = "certification"
    LINK = "link"
    CLAIM = "claim"


class VerificationStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EDITED = "edited"


class ExtractionRun(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "extraction_runs"

    source_document_id: Mapped[UUID] = mapped_column(
        ForeignKey("source_documents.id", ondelete="CASCADE")
    )
    status: Mapped[ExtractionStatus] = mapped_column(
        SqlEnum(
            ExtractionStatus,
            name="extraction_status",
            native_enum=False,
            values_callable=enum_values,
            validate_strings=True,
        )
    )
    model_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(255), nullable=True)
    input_sha256: Mapped[str] = mapped_column(String(64))
    output_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    source_document: Mapped["SourceDocument"] = relationship(back_populates="extraction_runs")
    fact_candidates: Mapped[list["FactCandidate"]] = relationship(
        back_populates="extraction_run",
        cascade="all, delete-orphan",
    )


class FactCandidate(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "fact_candidates"

    extraction_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("extraction_runs.id", ondelete="CASCADE")
    )
    profile_id: Mapped[UUID] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"))
    candidate_kind: Mapped[CandidateKind] = mapped_column(
        SqlEnum(
            CandidateKind,
            name="candidate_kind",
            native_enum=False,
            values_callable=enum_values,
            validate_strings=True,
        )
    )
    parent_candidate_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("fact_candidates.id", ondelete="SET NULL"),
        nullable=True,
    )
    structured_data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    status: Mapped[VerificationStatus] = mapped_column(
        SqlEnum(
            VerificationStatus,
            name="verification_status",
            native_enum=False,
            values_callable=enum_values,
            validate_strings=True,
        ),
        default=VerificationStatus.PENDING,
    )
    reviewer_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    extraction_run: Mapped["ExtractionRun"] = relationship(back_populates="fact_candidates")
    profile: Mapped["Profile"] = relationship()
    parent_candidate: Mapped["FactCandidate | None"] = relationship(
        remote_side="FactCandidate.id",
        back_populates="child_candidates",
    )
    child_candidates: Mapped[list["FactCandidate"]] = relationship(back_populates="parent_candidate")
    evidence_spans: Mapped[list["FactEvidenceSpan"]] = relationship(
        back_populates="fact_candidate",
        cascade="all, delete-orphan",
    )
    approved_claims: Mapped[list["ApprovedClaim"]] = relationship(
        back_populates="approved_from_candidate"
    )
    verification_events: Mapped[list["VerificationEvent"]] = relationship(
        back_populates="fact_candidate"
    )


class FactEvidenceSpan(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "fact_evidence_spans"

    source_document_id: Mapped[UUID] = mapped_column(
        ForeignKey("source_documents.id", ondelete="CASCADE")
    )
    fact_candidate_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("fact_candidates.id", ondelete="CASCADE"),
        nullable=True,
    )
    source_text_start: Mapped[int] = mapped_column()
    source_text_end: Mapped[int] = mapped_column()
    snippet_text: Mapped[str] = mapped_column(Text)
    confidence_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    fact_candidate: Mapped["FactCandidate | None"] = relationship(back_populates="evidence_spans")
    source_document: Mapped["SourceDocument"] = relationship()
