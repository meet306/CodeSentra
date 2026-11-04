"""
HMAC SHA-256 Signature Verification for GitHub Webhook Events.
Defends against forged webhook payloads using constant-time comparison.
"""

import hashlib
import hmac

from app.core.errors import CodeSentraException
from app.core.logging import logger


class InvalidWebhookSignatureError(CodeSentraException):
    """Raised when GitHub webhook signature verification fails."""

    def __init__(self, message: str = "Invalid GitHub webhook signature."):
        super().__init__(message=message, status_code=401)


def verify_github_signature(
    payload_body: bytes,
    signature_header: str | None,
    secret: str | None,
) -> bool:
    """Verifies that the webhook payload was signed by GitHub using the shared secret.

    Uses hmac.compare_digest for constant-time comparison to prevent timing attacks.
    """
    if not secret:
        logger.warning(
            "GITHUB_WEBHOOK_SECRET is not configured. Webhook signature verification bypassed for local development."
        )
        return True

    if not signature_header:
        logger.error("Missing X-Hub-Signature-256 header in webhook request.")
        raise InvalidWebhookSignatureError("Missing X-Hub-Signature-256 header.")

    if not signature_header.startswith("sha256="):
        logger.error("Invalid signature format; expected 'sha256=<hex>'")
        raise InvalidWebhookSignatureError("Invalid signature algorithm prefix.")

    expected_signature = "sha256=" + hmac.new(
        key=secret.encode("utf-8"),
        msg=payload_body,
        digestmod=hashlib.sha256,
    ).hexdigest()

    is_valid = hmac.compare_digest(expected_signature, signature_header)
    if not is_valid:
        logger.error("HMAC signature mismatch for incoming webhook.")
        raise InvalidWebhookSignatureError("HMAC SHA-256 signature mismatch.")

    return True
