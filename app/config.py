"""
Application Configuration using Pydantic Settings.
Reads from environment variables and .env file.
"""

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Core settings for CodeSentra PR Reviewer."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # General Application Settings
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"
    APP_NAME: str = "CodeSentra AI PR Reviewer"
    API_V1_PREFIX: str = "/api/v1"

    # Groq API Configuration (Free Tier)
    GROQ_API_KEY: str | None = Field(default=None, description="Groq API Key (Free tier)")
    GROQ_MODEL: str = Field(default="qwen/qwen3.8-27b", description="Default Groq LLM model")
    GROQ_MAX_RETRIES: int = Field(default=3, description="Max retries for rate-limited requests")
    GROQ_TIMEOUT_SECONDS: float = Field(default=30.0, description="HTTP timeout for Groq API calls")

    # GitHub Integration
    GITHUB_TOKEN: str | None = Field(default=None, description="GitHub Personal Access Token or fallback token")
    GITHUB_API_BASE_URL: str = Field(default="https://api.github.com", description="GitHub REST API Base URL")
    GITHUB_WEBHOOK_SECRET: str | None = Field(default=None, description="HMAC SHA-256 Webhook secret")
    GITHUB_APP_ID: str | None = Field(default=None, description="GitHub App ID")
    GITHUB_APP_PRIVATE_KEY: str | None = Field(default=None, description="GitHub App Private Key (PEM string or path)")
    GITHUB_APP_INSTALLATION_ID: str | None = Field(default=None, description="Default installation ID if applicable")

    @field_validator("GITHUB_TOKEN", "GROQ_API_KEY", "GITHUB_WEBHOOK_SECRET", mode="before")
    @classmethod
    def clean_placeholders(cls, v: str | None) -> str | None:
        if v and ("your_" in v.lower() or v.strip() == ""):
            return None
        return v

    # Review Settings
    DRY_RUN: bool = Field(default=True, description="When true, review findings are not posted to GitHub")
    MAX_DIFF_LINES: int = Field(default=1200, description="Max diff lines processed to stay within free-tier limits")
    MAX_DIFF_FILES: int = Field(default=25, description="Max number of files per PR to review")
    MAX_TOKENS_PER_CHUNK: int = Field(default=3000, description="Chunk size limit for diff analysis")

    # Database & Redis Settings
    DATABASE_URL: str = Field(
        default="sqlite+aiosqlite:///./codesentra.db",
        description="Async database connection string (PostgreSQL with asyncpg or SQLite fallback)",
    )
    REDIS_URL: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL for Celery background tasks",
    )

    # Optional Telemetry & Observability (Langfuse self-hosted)
    LANGFUSE_PUBLIC_KEY: str | None = Field(default=None, description="Langfuse public key")
    LANGFUSE_SECRET_KEY: str | None = Field(default=None, description="Langfuse secret key")
    LANGFUSE_HOST: str = Field(default="http://localhost:3000", description="Self-hosted Langfuse host")


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings singleton."""
    return Settings()
