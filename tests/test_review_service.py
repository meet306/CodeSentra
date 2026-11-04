"""
Unit tests for the Phase 1 ReviewService.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.config import Settings
from app.integrations.github import GitHubClient
from app.integrations.groq import GroqClient
from app.schemas.github import PRDetails, PRDiffData
from app.schemas.review import ReviewRequest, Severity
from app.services.reviewer.review_service import ReviewService


@pytest.mark.asyncio
async def test_review_service_happy_path(
    test_settings: Settings,
    sample_diff_data: PRDiffData,
) -> None:
    """Verifies complete review orchestration from diff to structured response."""
    mock_github = MagicMock(spec=GitHubClient)
    mock_github.get_complete_pr_diff_data = AsyncMock(return_value=sample_diff_data)

    mock_groq = MagicMock(spec=GroqClient)
    mock_groq_response = {
        "data": {
            "overview": "Identified security flaw in password hashing routine.",
            "findings": [
                {
                    "title": "Use of weak cryptographic hash (MD5)",
                    "description": "MD5 should not be used for hashing passwords.",
                    "severity": "HIGH",
                    "confidence": 0.95,
                    "file_path": "src/auth.py",
                    "line_number": 5,
                    "code_snippet": "return hashlib.md5(password.encode()).hexdigest()",
                    "suggested_fix": "Use argon2 or bcrypt instead.",
                    "reasoning": "MD5 lacks collision resistance and work factor.",
                }
            ],
        },
        "usage": {"prompt_tokens": 250, "completion_tokens": 120, "total_tokens": 370},
        "model": "llama-3.3-70b-versatile",
    }
    mock_groq.generate_completion_with_retry = AsyncMock(return_value=mock_groq_response)
    # Use real parsing logic on the mock client
    real_groq = GroqClient(settings=test_settings)
    mock_groq.parse_findings_from_dict = real_groq.parse_findings_from_dict

    service = ReviewService(
        github_client=mock_github,
        groq_client=mock_groq,
        settings=test_settings,
    )

    request = ReviewRequest(
        repo_owner="octocat",
        repo_name="Hello-World",
        pr_number=42,
        dry_run=True,
    )

    response = await service.review_pull_request(request)

    assert response.repo == "octocat/Hello-World"
    assert response.pr_number == 42
    assert response.status == "completed"
    assert response.dry_run is True
    assert response.summary.total_findings == 1
    assert response.summary.high_count == 1
    assert len(response.findings) == 1
    assert response.findings[0].severity == Severity.HIGH
    assert response.findings[0].file_path == "src/auth.py"
    assert response.findings[0].line_number == 5
    assert response.tokens_consumed["total_tokens"] == 370


@pytest.mark.asyncio
async def test_review_service_empty_diff(test_settings: Settings) -> None:
    """Verifies that an empty PR diff produces a clean zero-finding response without calling Groq."""
    empty_diff_data = PRDiffData(
        pr_details=PRDetails(
            owner="octocat",
            repo="Hello-World",
            pull_number=1,
            title="Empty PR",
            base_ref="main",
            head_ref="empty",
            base_sha="abc",
            head_sha="def",
            author="octocat",
            html_url="https://github.com/octocat/Hello-World/pull/1",
        ),
        files=[],
        raw_diff="",
        total_files=0,
        total_additions=0,
        total_deletions=0,
    )

    mock_github = MagicMock(spec=GitHubClient)
    mock_github.get_complete_pr_diff_data = AsyncMock(return_value=empty_diff_data)

    mock_groq = MagicMock(spec=GroqClient)
    mock_groq.generate_completion_with_retry = AsyncMock()

    service = ReviewService(
        github_client=mock_github,
        groq_client=mock_groq,
        settings=test_settings,
    )

    request = ReviewRequest(repo_owner="octocat", repo_name="Hello-World", pr_number=1)
    response = await service.review_pull_request(request)

    assert response.summary.total_findings == 0
    assert "No file changes" in response.summary.overview
    assert len(response.findings) == 0
    # Groq should NOT be called when diff is empty
    mock_groq.generate_completion_with_retry.assert_not_called()
