from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from careeros.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from careeros.db.models.profile import Profile
    from careeros.db.models.source_document import SourceDocument


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str | None] = mapped_column(String(320), unique=True, nullable=True)
    display_name: Mapped[str] = mapped_column(String(255))
    timezone: Mapped[str] = mapped_column(String(64))
    api_token_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)

    profiles: Mapped[list["Profile"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    source_documents: Mapped[list["SourceDocument"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )

