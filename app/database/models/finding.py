"""
Agent Finding database model.
"""

from typing import TYPE_CHECKING

from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.database.models.review_session import ReviewSession


class AgentFinding(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Stores individual structured findings emitted by review agents."""

    __tablename__ = "agent_findings"

    review_session_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("review_sessions.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    agent_name: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(String(20), index=True, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.8, nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), index=True, nullable=False)
    line_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    code_snippet: Mapped[str | None] = mapped_column(Text, nullable=True)
    suggested_fix: Mapped[str | None] = mapped_column(Text, nullable=True)
    reasoning: Mapped[str] = mapped_column(Text, nullable=False)

    # Relationships
    review_session: Mapped["ReviewSession"] = relationship("ReviewSession", back_populates="findings")
