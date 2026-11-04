"""
User database model.
"""

from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.database.models.developer_feedback import DeveloperFeedback


class User(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Represents a GitHub user / PR author / reviewer."""

    __tablename__ = "users"

    github_username: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Relationships
    feedbacks: Mapped[list["DeveloperFeedback"]] = relationship(
        "DeveloperFeedback",
        back_populates="user",
        cascade="all, delete-orphan",
    )
