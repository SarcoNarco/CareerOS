from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, Enum as SqlEnum, ForeignKey, Index, SmallInteger, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from careeros.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, enum_values

if TYPE_CHECKING:
    from careeros.db.models.internship import Internship
    from careeros.db.models.matching import InternshipMatch
    from careeros.db.models.profile import Profile


class ApplicationStatus(str, Enum):
    SAVED = "saved"
    APPLYING = "applying"
    APPLIED = "applied"
    INTERVIEW = "interview"
    REJECTED = "rejected"
    OFFER = "offer"
    CLOSED = "closed"
    IGNORED = "ignored"


class ApplicationRecord(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "application_records"
    __table_args__ = (
        Index("ix_application_records_profile_status", "profile_id", "status"),
        Index("ix_application_records_profile_priority", "profile_id", "priority"),
        Index("ix_application_records_internship_id", "internship_id"),
    )

    profile_id: Mapped[UUID] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"))
    internship_id: Mapped[UUID] = mapped_column(ForeignKey("internships.id", ondelete="CASCADE"))
    internship_match_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("internship_matches.id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[ApplicationStatus] = mapped_column(
        SqlEnum(
            ApplicationStatus,
            name="application_status",
            native_enum=False,
            values_callable=enum_values,
            validate_strings=True,
        )
    )
    priority: Mapped[int] = mapped_column(SmallInteger, default=3)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_action_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    profile: Mapped["Profile"] = relationship()
    internship: Mapped["Internship"] = relationship()
    internship_match: Mapped["InternshipMatch | None"] = relationship()
