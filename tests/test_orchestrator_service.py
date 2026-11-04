"""
Unit tests for the LangGraph OrchestratorService.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.config import Settings
from app.integrations.github import GitHubClient
from app.integrations.groq import GroqClient
from app.schemas.github import PRDiffData
from app.schemas.review import ReviewRequest, Severity
from app.services.orchestrator.orchestrator_service import OrchestratorService


@pytest.mark.asyncio
async def test_orchestrator_runs_multi_agent_workflow(
    test_settings: Settings,
    sample_diff_data: PRDiffData,
) -> None:
    """Verifies complete LangGraph multi-agent orchestration across all 4 agents."""
    mock_github = MagicMock(spec=GitHubClient)
    mock_github.get_complete_pr_diff_data = AsyncMock(return_value=sample_diff_data)

    mock_groq = MagicMock(spec=GroqClient)
    real_groq = GroqClient(settings=test_settings)
    mock_groq.parse_findings_from_dict = real_groq.parse_findings_from_dict

    # Each agent call returns one finding
    mock_groq.generate_completion_with_retry = AsyncMock(
        side_effect=[
            # Static Agent
            {"data": {"findings": [{"title": "Bug", "severity": "HIGH", "file_path": "src/auth.py", "reasoning": "r1"}]}},
            # Security Agent
            {"data": {"findings": [{"title": "OWASP Injection", "severity": "CRITICAL", "file_path": "src/auth.py", "reasoning": "r2"}]}},
            # Architecture Agent
            {"data": {"findings": []}},
            # Style Agent
            {"data": {"findings": [{"title": "Readability", "severity": "INFO", "file_path": "src/auth.py", "reasoning": "r3"}]}},
        ]
    )

    orchestrator = OrchestratorService(
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

    response = await orchestrator.execute_multi_agent_review(request)

    assert response.repo == "octocat/Hello-World"
    assert response.pr_number == 42
    assert response.status == "completed"
    assert response.summary.total_findings == 3
    assert response.summary.critical_count == 1
    assert response.summary.high_count == 1
    assert response.summary.info_count == 1
    assert len(response.findings) == 3
    # Critical should be ranked first
    assert response.findings[0].severity == Severity.CRITICAL
    assert "OWASP Injection" in response.findings[0].title
