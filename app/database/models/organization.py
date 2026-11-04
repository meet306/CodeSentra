"""
Organization database model.
"""

from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.database.models.repository import Repository


class Organization(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Represents a customer organization or GitHub account boundary."""

    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String(150), unique=True, index=True, nullable=False)
    slug: Mapped[str] = mapped_column(String(150), unique=True, index=True, nullable=False)
    github_org_id: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)

    # Relationships
    repositories: Mapped[list["Repository"]] = relationship(
        "Repository",
        back_populates="organization",
        cascade="all, delete-orphan",
    )
