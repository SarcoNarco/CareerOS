from typing import TYPE_CHECKING, Any

from uuid import UUID

from sqlalchemy import ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from careeros.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from careeros.db.models.user import User


class Profile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "profiles"

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    headline: Mapped[str | None] = mapped_column(String(255), nullable=True)
    summary: Mapped[str | None] = mapped_column(String, nullable=True)
    target_roles: Mapped[list[str]] = mapped_column(JSON, default=list)
    target_locations: Mapped[list[str]] = mapped_column(JSON, default=list)
    work_preferences: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    user: Mapped["User"] = relationship(back_populates="profiles")
