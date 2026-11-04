"""
Unit tests for the Groq Free Tier LLM client integration.
"""

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from groq import RateLimitError

from app.config import Settings
from app.core.errors import GroqAPIError
from app.integrations.groq import GroqClient
from app.schemas.review import Severity


def test_groq_missing_api_key() -> None:
    """Verifies that accessing client without GROQ_API_KEY raises a clear error."""
    settings = Settings(GROQ_API_KEY=None)
    client = GroqClient(settings=settings)
    with pytest.raises(GroqAPIError) as exc_info:
        _ = client.client
    assert "GROQ_API_KEY is not set" in exc_info.value.message


def test_parse_findings_valid(test_settings: Settings) -> None:
    """Verifies safe parsing and schema validation of model responses."""
    client = GroqClient(settings=test_settings)
    raw_payload = {
        "findings": [
            {
                "title": "SQL Injection",
                "description": "Raw string concatenation in SQL query",
                "severity": "CRITICAL",
                "confidence": 0.98,
                "file_path": "models/user.py",
                "line_number": 42,
                "code_snippet": 'f"SELECT * FROM users WHERE id = {user_id}"',
                "suggested_fix": "Use parameterized queries with SQLAlchemy",
                "reasoning": "Direct formatting inside query string allows injection",
            }
        ]
    }

    findings = client.parse_findings_from_dict(
        raw_data=raw_payload,
        agent_name="security_tester",
        valid_files=["models/user.py"],
    )

    assert len(findings) == 1
    f = findings[0]
    assert f.title == "SQL Injection"
    assert f.severity == Severity.CRITICAL
    assert f.confidence == 0.98
    assert f.file_path == "models/user.py"
    assert f.line_number == 42


def test_parse_findings_rejects_hallucinated_file(test_settings: Settings) -> None:
    """Verifies that findings referencing non-existent files are safely dropped."""
    client = GroqClient(settings=test_settings)
    raw_payload = {
        "findings": [
            {
                "title": "Phantom Bug",
                "description": "Issue in a hallucinated file",
                "severity": "MEDIUM",
                "file_path": "does_not_exist.py",
                "line_number": 10,
                "reasoning": "Hallucinated reasoning",
            }
        ]
    }

    findings = client.parse_findings_from_dict(
        raw_data=raw_payload,
        agent_name="tester",
        valid_files=["app/main.py", "app/config.py"],
    )

    assert len(findings) == 0


def test_parse_findings_handles_empty_or_malformed(test_settings: Settings) -> None:
    """Verifies parsing returns an empty list for missing or invalid findings key."""
    client = GroqClient(settings=test_settings)
    assert client.parse_findings_from_dict({}, valid_files=["app.py"]) == []
    assert client.parse_findings_from_dict({"findings": "not-a-list"}, valid_files=["app.py"]) == []


@pytest.mark.asyncio
async def test_completion_retry_on_rate_limit(test_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifies exponential backoff retry mechanism when encountering 429 RateLimitError."""
    test_settings.GROQ_MAX_RETRIES = 2
    client = GroqClient(settings=test_settings)

    mock_groq_sdk = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = '{"overview": "Great PR", "findings": []}'
    mock_response.usage.prompt_tokens = 100
    mock_response.usage.completion_tokens = 50
    mock_response.usage.total_tokens = 150
    mock_response.model = "llama-3.3-70b-versatile"

    # Simulate 1 RateLimitError followed by success
    dummy_req = httpx.Request("POST", "https://api.groq.com")
    dummy_resp = httpx.Response(429, request=dummy_req)
    mock_groq_sdk.chat.completions.create = AsyncMock(
        side_effect=[
            RateLimitError("Rate limit exceeded", response=dummy_resp, body=None),
            mock_response,
        ]
    )

    client._client = mock_groq_sdk

    # Patch asyncio.sleep inside app.integrations.groq to avoid sleeping during tests
    monkeypatch.setattr("app.integrations.groq.asyncio.sleep", AsyncMock())

    result = await client.generate_completion_with_retry([{"role": "user", "content": "hi"}])
    assert result["data"]["overview"] == "Great PR"
    assert result["usage"]["total_tokens"] == 150
    assert mock_groq_sdk.chat.completions.create.call_count == 2
