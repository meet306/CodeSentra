"""
Standard application exceptions and error models.
"""

from typing import Any


class CodeSentraException(Exception):
    """Base exception for all CodeSentra domain errors."""

    def __init__(self, message: str, status_code: int = 500, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.details = details or {}


class GitHubAPIError(CodeSentraException):
    """Raised when GitHub REST API fails or returns an error."""

    def __init__(self, message: str, status_code: int = 502, details: dict[str, Any] | None = None):
        super().__init__(f"GitHub API Error: {message}", status_code=status_code, details=details)


class GroqAPIError(CodeSentraException):
    """Raised when Groq API encounters a network, model, or rate-limit failure."""

    def __init__(self, message: str, status_code: int = 502, details: dict[str, Any] | None = None):
        super().__init__(f"Groq API Error: {message}", status_code=status_code, details=details)


class RateLimitExceededError(CodeSentraException):
    """Raised when Groq or GitHub rate limits are reached."""

    def __init__(self, message: str = "Rate limit reached. Please retry after backoff.", details: dict[str, Any] | None = None):
        super().__init__(message, status_code=429, details=details)


class DiffParsingError(CodeSentraException):
    """Raised when git diff format cannot be parsed."""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(f"Diff Parsing Error: {message}", status_code=400, details=details)
