"""
Pull Request database model.
"""

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.database.models.repository import Repository
    from app.database.models.review_session import ReviewSession


class PullRequest(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Tracks Pull Request history, branch states, and review sessions."""

    __tablename__ = "pull_requests"

    repository_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("repositories.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    pull_number: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    author: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    base_ref: Mapped[str] = mapped_column(String(100), nullable=False)
    head_ref: Mapped[str] = mapped_column(String(100), nullable=False)
    head_sha: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    state: Mapped[str] = mapped_column(String(30), default="open", nullable=False)
    is_merged: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    repository: Mapped["Repository"] = relationship("Repository", back_populates="pull_requests")
    review_sessions: Mapped[list["ReviewSession"]] = relationship(
        "ReviewSession",
        back_populates="pull_request",
        cascade="all, delete-orphan",
    )
