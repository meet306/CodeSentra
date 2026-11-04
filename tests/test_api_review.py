"""
Integration tests for the /api/v1/review/pr endpoint.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.dependencies import get_review_service
from app.core.errors import GitHubAPIError, RateLimitExceededError
from app.main import create_application
from app.schemas.review import Finding, ReviewResponse, ReviewSummary, Severity
from app.services.reviewer.review_service import ReviewService


@pytest.mark.asyncio
async def test_api_review_pr_success() -> None:
    """Verifies that POST /api/v1/review/pr returns 200 with ReviewResponse payload."""
    app = create_application()
    mock_service = MagicMock(spec=ReviewService)

    sample_response = ReviewResponse(
        repo="octocat/Hello-World",
        pr_number=42,
        title="Fix bug",
        author="octocat",
        status="completed",
        dry_run=True,
        summary=ReviewSummary(
            total_findings=1,
            high_count=1,
            overview="Found 1 high severity issue",
        ),
        findings=[
            Finding(
                agent_name="phase1_ai_reviewer",
                title="Potential Null Pointer",
                description="Object may be null before access",
                severity=Severity.HIGH,
                confidence=0.9,
                file_path="src/main.py",
                line_number=10,
                reasoning="Variable is accessed without prior check",
            )
        ],
        execution_time_seconds=1.25,
        model_used="llama-3.3-70b-versatile",
    )
    mock_service.review_pull_request = AsyncMock(return_value=sample_response)

    app.dependency_overrides[get_review_service] = lambda: mock_service

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/review/pr",
            json={"repo_owner": "octocat", "repo_name": "Hello-World", "pr_number": 42},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["repo"] == "octocat/Hello-World"
    assert data["pr_number"] == 42
    assert data["summary"]["total_findings"] == 1
    assert data["findings"][0]["severity"] == "HIGH"


@pytest.mark.asyncio
async def test_api_review_pr_github_not_found() -> None:
    """Verifies that GitHubAPIError(404) returns 404 HTTP status."""
    app = create_application()
    mock_service = MagicMock(spec=ReviewService)
    mock_service.review_pull_request = AsyncMock(
        side_effect=GitHubAPIError("PR not found", status_code=404)
    )
    app.dependency_overrides[get_review_service] = lambda: mock_service

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/review/pr",
            json={"repo_owner": "unknown", "repo_name": "repo", "pr_number": 999},
        )

    assert response.status_code == 404
    assert "PR not found" in response.json()["detail"]


@pytest.mark.asyncio
async def test_api_review_pr_rate_limit_429() -> None:
    """Verifies that RateLimitExceededError returns 429 HTTP status."""
    app = create_application()
    mock_service = MagicMock(spec=ReviewService)
    mock_service.review_pull_request = AsyncMock(
        side_effect=RateLimitExceededError("Groq rate limit hit")
    )
    app.dependency_overrides[get_review_service] = lambda: mock_service

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/review/pr",
            json={"repo_owner": "octocat", "repo_name": "repo", "pr_number": 1},
        )

    assert response.status_code == 429
    assert "rate limit" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_api_review_pr_validation_error() -> None:
    """Verifies that invalid payload parameters return 422 Unprocessable Entity."""
    app = create_application()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/review/pr",
            json={"repo_owner": "octocat"},  # Missing repo_name and pr_number
        )

    assert response.status_code == 422
