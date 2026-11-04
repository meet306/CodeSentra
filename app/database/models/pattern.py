"""
Repository Learned Pattern database model.
"""

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.database.models.repository import Repository


class RepositoryPattern(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Stores repository-specific learned coding conventions and accepted rules."""

    __tablename__ = "repository_patterns"

    repository_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("repositories.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    pattern_category: Mapped[str] = mapped_column(String(50), nullable=False)
    rule_text: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.8, nullable=False)
    occurrences: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    repository: Mapped["Repository"] = relationship("Repository", back_populates="learned_patterns")
