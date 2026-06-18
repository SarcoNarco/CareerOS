from typing import TYPE_CHECKING
from uuid import UUID

from enum import Enum

from sqlalchemy import Enum as SqlEnum
from sqlalchemy import ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from careeros.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from careeros.db.models.extraction_run import ExtractionRun
    from careeros.db.models.user import User


class DocumentType(str, Enum):
    RESUME = "resume"
    TRANSCRIPT = "transcript"
    CERTIFICATE = "certificate"
    PORTFOLIO = "portfolio"
    MANUAL_NOTE = "manual_note"
    OTHER = "other"


class SourceDocument(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "source_documents"

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    document_type: Mapped[DocumentType] = mapped_column(
        SqlEnum(
            DocumentType,
            name="document_type",
            native_enum=False,
            validate_strings=True,
        )
    )
    file_name: Mapped[str] = mapped_column(String(255))
    storage_path: Mapped[str] = mapped_column(String(1024))
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict[str, str | int | None]] = mapped_column(JSON, default=dict)

    user: Mapped["User"] = relationship(back_populates="source_documents")
    extraction_runs: Mapped[list["ExtractionRun"]] = relationship(
        back_populates="source_document",
        cascade="all, delete-orphan",
    )
