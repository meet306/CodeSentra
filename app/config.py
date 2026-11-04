"""
Application Configuration using Pydantic Settings.
Reads from environment variables and .env file.
"""

from functools import lru_cache

from pydantic import Field
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
    GROQ_MODEL: str = Field(default="llama-3.3-70b-versatile", description="Default Groq LLM model")
    GROQ_MAX_RETRIES: int = Field(default=3, description="Max retries for rate-limited requests")
    GROQ_TIMEOUT_SECONDS: float = Field(default=30.0, description="HTTP timeout for Groq API calls")

    # GitHub Integration
    GITHUB_TOKEN: str | None = Field(default=None, description="GitHub Personal Access Token or App Token")
    GITHUB_API_BASE_URL: str = Field(default="https://api.github.com", description="GitHub REST API Base URL")

    # Review Settings
    DRY_RUN: bool = Field(default=True, description="When true, review findings are not posted to GitHub")
    MAX_DIFF_LINES: int = Field(default=1200, description="Max diff lines processed to stay within free-tier limits")
    MAX_DIFF_FILES: int = Field(default=25, description="Max number of files per PR to review")
    MAX_TOKENS_PER_CHUNK: int = Field(default=3000, description="Chunk size limit for diff analysis")


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings singleton."""
    return Settings()
