"""
Agent Execution Log database model.
"""

from typing import TYPE_CHECKING

from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.database.models.review_session import ReviewSession


class AgentExecutionLog(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Tracks per-agent execution metrics, durations, and errors."""

    __tablename__ = "agent_execution_logs"

    review_session_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("review_sessions.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    agent_name: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    duration_seconds: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="SUCCESS", nullable=False)
    findings_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    review_session: Mapped["ReviewSession"] = relationship("ReviewSession", back_populates="execution_logs")
