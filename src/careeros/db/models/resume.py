from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Enum as SqlEnum, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from careeros.db.base import Base, UUIDPrimaryKeyMixin, enum_values, utc_now

if TYPE_CHECKING:
    from careeros.db.models.internship import Internship
    from careeros.db.models.profile import Profile
    from careeros.db.models.verification import ApprovedClaim


class ResumeStatus(str, Enum):
    DRAFT = "draft"
    APPROVED = "approved"
    EXPORTED = "exported"


class ResumeTemplate(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "resume_templates"

    name: Mapped[str] = mapped_column(String(255), unique=True)
    template_engine: Mapped[str] = mapped_column(String(64))
    template_path: Mapped[str] = mapped_column(String(1024))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    generated_resumes: Mapped[list["GeneratedResume"]] = relationship(back_populates="template")


class GeneratedResume(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "generated_resumes"
    __table_args__ = (
        Index("ix_generated_resumes_profile_created_at", "profile_id", "created_at"),
    )

    profile_id: Mapped[UUID] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"))
    internship_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("internships.id", ondelete="SET NULL"),
        nullable=True,
    )
    template_id: Mapped[UUID] = mapped_column(ForeignKey("resume_templates.id", ondelete="RESTRICT"))
    status: Mapped[ResumeStatus] = mapped_column(
        SqlEnum(
            ResumeStatus,
            name="resume_status",
            native_enum=False,
            values_callable=enum_values,
            validate_strings=True,
        )
    )
    rendered_html_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    rendered_pdf_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    profile: Mapped["Profile"] = relationship()
    internship: Mapped["Internship | None"] = relationship()
    template: Mapped["ResumeTemplate"] = relationship(back_populates="generated_resumes")
    claim_links: Mapped[list["GeneratedResumeClaim"]] = relationship(
        back_populates="generated_resume",
        cascade="all, delete-orphan",
    )


class GeneratedResumeClaim(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "generated_resume_claims"
    __table_args__ = (
        Index(
            "ix_generated_resume_claims_resume_order",
            "generated_resume_id",
            "display_order",
        ),
    )

    generated_resume_id: Mapped[UUID] = mapped_column(
        ForeignKey("generated_resumes.id", ondelete="CASCADE")
    )
    approved_claim_id: Mapped[UUID] = mapped_column(
        ForeignKey("approved_claims.id", ondelete="RESTRICT")
    )
    section_name: Mapped[str] = mapped_column(String(128))
    display_order: Mapped[int] = mapped_column(Integer)
    rendered_text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    generated_resume: Mapped["GeneratedResume"] = relationship(back_populates="claim_links")
    approved_claim: Mapped["ApprovedClaim"] = relationship()
