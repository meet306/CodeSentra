"""
Unit tests for GitHubReviewPoster.
"""

from unittest.mock import AsyncMock

import httpx
import pytest

from app.config import Settings
from app.schemas.review import Finding, ReviewResponse, ReviewSummary, Severity
from app.services.reviewer.github_poster import GitHubReviewPoster


@pytest.fixture
def sample_review_response() -> ReviewResponse:
    return ReviewResponse(
        repo="octocat/Hello-World",
        pr_number=5,
        title="Add payment route",
        author="alice",
        dry_run=True,
        summary=ReviewSummary(
            total_findings=1,
            critical_count=1,
            overview="Found a critical security flaw.",
        ),
        findings=[
            Finding(
                agent_name="security_agent",
                title="SQL Injection",
                description="Raw concatenation in database query",
                severity=Severity.CRITICAL,
                confidence=0.98,
                file_path="src/pay.py",
                line_number=20,
                code_snippet="SELECT * FROM pay WHERE id = " + "{id}",
                suggested_fix="Use parameterized query",
                reasoning="Diff demonstrates unescaped string formatting",
            )
        ],
        execution_time_seconds=1.2,
        model_used="llama-3.3-70b-versatile",
    )


def test_format_review_markdown(test_settings: Settings, sample_review_response: ReviewResponse) -> None:
    poster = GitHubReviewPoster(settings=test_settings)
    md = poster.format_review_markdown(sample_review_response)

    assert "CodeSentra AI Pull Request Review" in md
    assert "SQL Injection" in md
    assert "CRITICAL" in md
    assert "`src/pay.py`:L20" in md
    assert "Suggested Fix" in md


@pytest.mark.asyncio
async def test_post_review_dry_run_mode(test_settings: Settings, sample_review_response: ReviewResponse) -> None:
    test_settings.DRY_RUN = True
    poster = GitHubReviewPoster(settings=test_settings)

    result = await poster.post_review(
        owner="octocat",
        repo="Hello-World",
        pull_number=5,
        review=sample_review_response,
    )

    assert result["posted"] is False
    assert result["dry_run"] is True
    assert "not published" in result["message"]


@pytest.mark.asyncio
async def test_post_review_live_mode(
    test_settings: Settings,
    sample_review_response: ReviewResponse,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    test_settings.DRY_RUN = False
    sample_review_response.dry_run = False
    poster = GitHubReviewPoster(settings=test_settings)

    mock_resp = httpx.Response(
        status_code=200,
        json={"id": 12345, "html_url": "https://github.com/octocat/Hello-World/pull/5#pullrequestreview-12345"},
        request=httpx.Request("POST", "https://api.github.com"),
    )
    monkeypatch.setattr(httpx.AsyncClient, "post", AsyncMock(return_value=mock_resp))

    result = await poster.post_review(
        owner="octocat",
        repo="Hello-World",
        pull_number=5,
        review=sample_review_response,
        auth_token="ghp_test_token_12345",
        commit_sha="abcdef12345",
    )

    assert result["posted"] is True
    assert result["dry_run"] is False
    assert result["review_id"] == 12345
    assert "https://github.com/octocat/Hello-World/pull/5" in result["url"]
