"""
Unit tests for the HMAC SHA-256 Webhook Signature Verifier.
"""

import hashlib
import hmac

import pytest

from app.services.gateway.verifier import InvalidWebhookSignatureError, verify_github_signature


def test_verify_valid_signature() -> None:
    secret = "test_webhook_secret_key"
    payload = b'{"action": "opened", "pull_request": {"number": 1}}'
    expected_hex = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    valid_header = f"sha256={expected_hex}"

    assert verify_github_signature(payload, valid_header, secret) is True


def test_verify_invalid_signature_raises_error() -> None:
    secret = "test_webhook_secret_key"
    payload = b'{"action": "opened"}'
    invalid_header = "sha256=0000000000000000000000000000000000000000000000000000000000000000"

    with pytest.raises(InvalidWebhookSignatureError) as exc_info:
        verify_github_signature(payload, invalid_header, secret)

    assert exc_info.value.status_code == 401
    assert "mismatch" in exc_info.value.message.lower()


def test_verify_missing_signature_raises_error() -> None:
    secret = "test_webhook_secret_key"
    payload = b'{"action": "opened"}'

    with pytest.raises(InvalidWebhookSignatureError) as exc_info:
        verify_github_signature(payload, None, secret)

    assert exc_info.value.status_code == 401
    assert "Missing" in exc_info.value.message


def test_verify_no_secret_bypasses_check() -> None:
    payload = b'{"action": "opened"}'
    # When no secret configured (local dev), returns True
    assert verify_github_signature(payload, None, None) is True
