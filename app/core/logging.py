"""
Sanitized logging setup to prevent leaking API keys, tokens, or confidential data.
"""

import logging
import re
import sys

# Patterns to mask sensitive data
SENSITIVE_PATTERNS = [
    re.compile(r"(gsk_[A-Za-z0-9_-]{20,})", re.IGNORECASE),  # Groq API keys
    re.compile(r"(ghp_[A-Za-z0-9]{36,})", re.IGNORECASE),    # GitHub Personal Access Tokens
    re.compile(r"(github_pat_[A-Za-z0-9_]{50,})", re.IGNORECASE), # Fine-grained GitHub tokens
    re.compile(r"(Bearer\s+)[A-Za-z0-9_\-\.]{15,}", re.IGNORECASE), # Bearer tokens
    re.compile(r"(token=)[A-Za-z0-9_\-\.]{15,}", re.IGNORECASE),
]


class SecretMaskingFormatter(logging.Formatter):
    """Custom logging formatter that masks secrets and credentials."""

    def format(self, record: logging.LogRecord) -> str:
        original = super().format(record)
        masked = original
        for pattern in SENSITIVE_PATTERNS:
            masked = pattern.sub(r"[REDACTED_SECRET]", masked)
        return masked


def setup_logger(name: str = "codesentra", level: str = "INFO") -> logging.Logger:
    """Configures and returns a sanitized logger."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = SecretMaskingFormatter(
            fmt="%(asctime)s | %(levelname)-7s | %(name)s:%(lineno)d - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    log_level = getattr(logging, level.upper(), logging.INFO)
    logger.setLevel(log_level)
    return logger


logger = setup_logger()
