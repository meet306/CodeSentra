"""
Unit tests for WebhookProcessor and PR event handling.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.config import Settings
from app.schemas.review import ReviewResponse, ReviewSummary
from app.services.orchestrator.orchestrator_service import OrchestratorService
from app.services.reviewer.github_poster import GitHubReviewPoster
from app.services.webhook.processor import WebhookProcessor


@pytest.mark.asyncio
async def test_webhook_processor_pr_opened(test_settings: Settings) -> None:
    """Verifies that an 'opened' PR event executes the orchestrator review."""
    mock_orchestrator = MagicMock(spec=OrchestratorService)
    mock_poster = MagicMock(spec=GitHubReviewPoster)

    mock_review_response = ReviewResponse(
        repo="octocat/Hello-World",
        pr_number=10,
        title="Test PR",
        author="octocat",
        dry_run=True,
        summary=ReviewSummary(total_findings=0, overview="Clean"),
        findings=[],
        execution_time_seconds=0.5,
        model_used="llama-3.3-70b-versatile",
    )
    mock_orchestrator.execute_multi_agent_review = AsyncMock(return_value=mock_review_response)
    mock_poster.post_review = AsyncMock(return_value={"posted": False, "dry_run": True})

    processor = WebhookProcessor(
        orchestrator=mock_orchestrator,
        poster=mock_poster,
        settings=test_settings,
    )

    payload = {
        "action": "opened",
        "repository": {"name": "Hello-World", "owner": {"login": "octocat"}},
        "pull_request": {"number": 10, "head": {"sha": "abc12345"}},
    }

    result = await processor.process_pull_request_event(payload, delivery_id="delivery-001")

    assert result["status"] == "reviewed"
    assert result["pr_number"] == 10
    mock_orchestrator.execute_multi_agent_review.assert_called_once()
    mock_poster.post_review.assert_called_once()


@pytest.mark.asyncio
async def test_webhook_processor_idempotency(test_settings: Settings) -> None:
    """Verifies that a duplicate webhook delivery is safely ignored."""
    processor = WebhookProcessor(settings=test_settings)
    payload = {
        "action": "synchronize",
        "repository": {"name": "Hello-World", "owner": {"login": "octocat"}},
        "pull_request": {"number": 10, "head": {"sha": "abc12345"}},
    }

    # First call records delivery
    assert processor.is_duplicate_event("delivery-abc") is False
    # Second call with same ID detects duplicate
    assert processor.is_duplicate_event("delivery-abc") is True

    result = await processor.process_pull_request_event(payload, delivery_id="delivery-abc")
    assert result["status"] == "skipped"
    assert "already processed" in result["reason"]


@pytest.mark.asyncio
async def test_webhook_processor_merged_pr(
    test_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verifies that closed PR with merged=True signals pattern learning."""
    processor = WebhookProcessor(settings=test_settings)
    payload = {
        "action": "closed",
        "repository": {"name": "Hello-World", "owner": {"login": "octocat"}},
        "pull_request": {"number": 12, "merged": True, "head": {"sha": "sha999"}},
    }

    from app.services.learner.learner_service import LearnerService
    mock_learn = AsyncMock(return_value=[{"rule_text": "pattern1", "category": "STYLE"}])
    monkeypatch.setattr(LearnerService, "learn_from_merged_pr", mock_learn)

    result = await processor.process_pull_request_event(payload)
    assert result["status"] == "learning_triggered"
    assert result["action"] == "merged"
    assert result["patterns_learned"] == 1
