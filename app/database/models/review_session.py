"""
Review Session database model.
"""

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.database.models.execution_log import AgentExecutionLog
    from app.database.models.finding import AgentFinding
    from app.database.models.pull_request import PullRequest
    from app.database.models.review_comment import ReviewComment


class ReviewSession(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Represents a discrete code review execution on a pull request."""

    __tablename__ = "review_sessions"

    pull_request_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("pull_requests.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(30), default="completed", nullable=False)
    execution_time_seconds: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    model_used: Mapped[str] = mapped_column(String(100), nullable=False)
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    overview: Mapped[str | None] = mapped_column(Text, nullable=True)
    dry_run: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    pull_request: Mapped["PullRequest"] = relationship("PullRequest", back_populates="review_sessions")
    findings: Mapped[list["AgentFinding"]] = relationship(
        "AgentFinding",
        back_populates="review_session",
        cascade="all, delete-orphan",
    )
    comments: Mapped[list["ReviewComment"]] = relationship(
        "ReviewComment",
        back_populates="review_session",
        cascade="all, delete-orphan",
    )
    execution_logs: Mapped[list["AgentExecutionLog"]] = relationship(
        "AgentExecutionLog",
        back_populates="review_session",
        cascade="all, delete-orphan",
    )
