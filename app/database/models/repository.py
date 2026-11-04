"""
Repository database model.
"""

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.database.models.organization import Organization
    from app.database.models.pattern import RepositoryPattern
    from app.database.models.pull_request import PullRequest


class Repository(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Represents a GitHub repository with organization isolation."""

    __tablename__ = "repositories"

    organization_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    owner: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(150), index=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    github_repo_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_private: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    default_branch: Mapped[str] = mapped_column(String(100), default="main", nullable=False)

    # Relationships
    organization: Mapped["Organization"] = relationship("Organization", back_populates="repositories")
    pull_requests: Mapped[list["PullRequest"]] = relationship(
        "PullRequest",
        back_populates="repository",
        cascade="all, delete-orphan",
    )
    learned_patterns: Mapped[list["RepositoryPattern"]] = relationship(
        "RepositoryPattern",
        back_populates="repository",
        cascade="all, delete-orphan",
    )
