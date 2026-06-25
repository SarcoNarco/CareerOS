from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, Enum as SqlEnum
from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from careeros.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, enum_values

if TYPE_CHECKING:
    from careeros.db.models.fact_staging import FactCandidate, FactEvidenceSpan
    from careeros.db.models.profile import Profile
    from careeros.db.models.source_document import SourceDocument
    from careeros.db.models.user import User


class ClaimStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    RETIRED = "retired"


class ApprovedClaim(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "approved_claims"

    profile_id: Mapped[UUID] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"))
    owning_entity_type: Mapped[str] = mapped_column(String(64))
    owning_entity_id: Mapped[UUID | None] = mapped_column(nullable=True)
    claim_text: Mapped[str] = mapped_column(Text)
    claim_type: Mapped[str] = mapped_column(String(64))
    status: Mapped[ClaimStatus] = mapped_column(
        SqlEnum(
            ClaimStatus,
            name="claim_status",
            native_enum=False,
            values_callable=enum_values,
            validate_strings=True,
        )
    )
    source_document_id: Mapped[UUID] = mapped_column(
        ForeignKey("source_documents.id", ondelete="CASCADE")
    )
    source_primary_span_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("fact_evidence_spans.id", ondelete="SET NULL"),
        nullable=True,
    )
    approved_from_candidate_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("fact_candidates.id", ondelete="SET NULL"),
        nullable=True,
    )
    approved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    profile: Mapped["Profile"] = relationship()
    source_document: Mapped["SourceDocument"] = relationship()
    source_primary_span: Mapped["FactEvidenceSpan | None"] = relationship()
    approved_from_candidate: Mapped["FactCandidate | None"] = relationship(
        back_populates="approved_claims",
        foreign_keys=[approved_from_candidate_id],
    )
    verification_events: Mapped[list["VerificationEvent"]] = relationship(
        back_populates="approved_claim",
        cascade="all, delete-orphan",
    )


class VerificationEvent(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "verification_events"

    fact_candidate_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("fact_candidates.id", ondelete="SET NULL"),
        nullable=True,
    )
    approved_claim_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("approved_claims.id", ondelete="SET NULL"),
        nullable=True,
    )
    actor_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    action: Mapped[str] = mapped_column(String(64))
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    fact_candidate: Mapped["FactCandidate | None"] = relationship(back_populates="verification_events")
    approved_claim: Mapped["ApprovedClaim | None"] = relationship(back_populates="verification_events")
    actor_user: Mapped["User"] = relationship()
