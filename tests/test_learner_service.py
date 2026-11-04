"""
Unit tests for the LearnerService and Developer Feedback system.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import Settings
from app.database.session import init_db
from app.integrations.github import GitHubClient
from app.integrations.groq import GroqClient
from app.main import create_application
from app.schemas.github import PRDiffData
from app.services.learner.learner_service import LearnerService


@pytest.mark.asyncio
async def test_learner_extracts_patterns_from_merged_pr(
    test_settings: Settings,
    sample_diff_data: PRDiffData,
) -> None:
    """Verifies that LearnerService extracts and persists repository patterns from merged PR diffs."""
    await init_db()

    mock_github = MagicMock(spec=GitHubClient)
    mock_github.get_complete_pr_diff_data = AsyncMock(return_value=sample_diff_data)

    mock_groq = MagicMock(spec=GroqClient)
    mock_groq.generate_completion_with_retry = AsyncMock(
        return_value={
            "data": {
                "patterns": [
                    {
                        "category": "STYLE",
                        "rule_text": "Prefer explicit type annotations on public functions",
                        "confidence": 0.9,
                    }
                ]
            }
        }
    )

    learner = LearnerService(
        github_client=mock_github,
        groq_client=mock_groq,
        settings=test_settings,
    )

    learned = await learner.learn_from_merged_pr("octocat", "Hello-World", 42)
    assert len(learned) == 1
    assert learned[0]["category"] == "STYLE"
    assert "explicit type annotations" in learned[0]["rule_text"]

    # Verify query retrieves active patterns
    active = await learner.get_active_patterns_for_repo("octocat/Hello-World")
    assert len(active) == 1
    assert "explicit type annotations" in active[0]


@pytest.mark.asyncio
async def test_record_developer_feedback(test_settings: Settings) -> None:
    """Verifies that developer feedback is recorded in the database."""
    await init_db()
    learner = LearnerService(settings=test_settings)

    result = await learner.record_feedback(
        repo_full_name="octocat/Hello-World",
        feedback_type="ACCEPTED",
        finding_id="finding-12345",
        comment="Great recommendation, applied in follow-up commit.",
    )

    assert result["status"] == "recorded"
    assert "feedback_id" in result


@pytest.mark.asyncio
async def test_api_submit_feedback() -> None:
    """Verifies POST /api/v1/feedback endpoint."""
    await init_db()
    app = create_application()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/feedback",
            json={
                "repo_full_name": "octocat/Hello-World",
                "feedback_type": "FALSE_POSITIVE",
                "finding_id": "find-001",
                "comment": "This is a test file, so mock secret is intentional.",
            },
        )

    assert response.status_code == 201
    assert response.json()["status"] == "recorded"
