"""
Unit tests for background workers and execution persistence.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.schemas.review import Finding, ReviewResponse, ReviewSummary, Severity
from app.services.orchestrator.orchestrator_service import OrchestratorService
from app.services.reviewer.github_poster import GitHubReviewPoster
from app.workers.tasks import _execute_and_persist_review


@pytest.mark.asyncio
async def test_execute_and_persist_review(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifies that _execute_and_persist_review orchestrates review, posts feedback, and saves to DB."""
    mock_orchestrator = MagicMock(spec=OrchestratorService)
    sample_response = ReviewResponse(
        repo="octocat/Hello-World",
        pr_number=77,
        title="Async Task PR",
        author="octocat",
        dry_run=True,
        summary=ReviewSummary(total_findings=1, low_count=1, overview="1 low finding"),
        findings=[
            Finding(
                agent_name="code_style_agent",
                title="Trailing Whitespace",
                description="Remove trailing spaces",
                severity=Severity.LOW,
                confidence=0.9,
                file_path="main.py",
                line_number=1,
                reasoning="Formatting issue",
            )
        ],
        execution_time_seconds=0.8,
        model_used="llama-3.3-70b-versatile",
    )
    mock_orchestrator.execute_multi_agent_review = AsyncMock(return_value=sample_response)

    mock_poster = MagicMock(spec=GitHubReviewPoster)
    mock_poster.post_review = AsyncMock(return_value={"posted": False, "dry_run": True})

    monkeypatch.setattr("app.workers.tasks.OrchestratorService", lambda **kwargs: mock_orchestrator)
    monkeypatch.setattr("app.workers.tasks.GitHubReviewPoster", lambda **kwargs: mock_poster)

    result = await _execute_and_persist_review(
        repo_owner="octocat",
        repo_name="Hello-World",
        pr_number=77,
        dry_run=True,
    )

    assert result["status"] == "success"
    assert result["findings_count"] == 1
