"""
GitHub App Installation model.
"""


from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class GitHubInstallation(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Represents a GitHub App installation on an account/repo."""

    __tablename__ = "github_installations"

    installation_id: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    account_login: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    account_type: Mapped[str] = mapped_column(String(50), default="User", nullable=False)
    permissions: Mapped[dict | None] = mapped_column(JSON, nullable=True)
