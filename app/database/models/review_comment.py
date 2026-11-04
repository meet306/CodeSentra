"""
Review Comment database model.
"""

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.database.models.review_session import ReviewSession


class ReviewComment(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Tracks comments and review summaries published to GitHub."""

    __tablename__ = "review_comments"

    review_session_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("review_sessions.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    github_review_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    github_comment_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    github_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    comment_type: Mapped[str] = mapped_column(String(50), default="PR_REVIEW", nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)

    # Relationships
    review_session: Mapped["ReviewSession"] = relationship("ReviewSession", back_populates="comments")
