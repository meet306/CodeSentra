"""
Unit tests for the GitHub REST API client integration.
"""

import httpx
import pytest
from pytest_mock import MockerFixture

from app.config import Settings
from app.core.errors import GitHubAPIError, RateLimitExceededError
from app.integrations.github import GitHubClient


@pytest.fixture
def github_client(test_settings: Settings) -> GitHubClient:
    return GitHubClient(settings=test_settings)


@pytest.mark.asyncio
async def test_get_pull_request_success(github_client: GitHubClient, mocker: MockerFixture) -> None:
    """Verifies successful retrieval and schema mapping of PR details."""
    mock_payload = {
        "title": "Add feature X",
        "body": "PR description",
        "state": "open",
        "base": {"ref": "main", "sha": "base123"},
        "head": {"ref": "feature-x", "sha": "head456"},
        "user": {"login": "alice"},
        "merged": False,
        "html_url": "https://github.com/test/repo/pull/1",
        "diff_url": "https://github.com/test/repo/pull/1.diff",
    }

    mock_response = httpx.Response(
        status_code=200,
        json=mock_payload,
        request=httpx.Request("GET", "https://api.github.com"),
    )
    mocker.patch("httpx.AsyncClient.get", return_value=mock_response)

    pr = await github_client.get_pull_request("test", "repo", 1)
    assert pr.owner == "test"
    assert pr.repo == "repo"
    assert pr.pull_number == 1
    assert pr.title == "Add feature X"
    assert pr.author == "alice"
    assert pr.base_ref == "main"
    assert pr.head_ref == "feature-x"
    assert not pr.is_merged


@pytest.mark.asyncio
async def test_get_pull_request_404(github_client: GitHubClient, mocker: MockerFixture) -> None:
    """Verifies that a 404 response raises GitHubAPIError with status 404."""
    mock_response = httpx.Response(
        status_code=404,
        json={"message": "Not Found"},
        request=httpx.Request("GET", "https://api.github.com"),
    )
    mocker.patch("httpx.AsyncClient.get", return_value=mock_response)

    with pytest.raises(GitHubAPIError) as exc_info:
        await github_client.get_pull_request("nonexistent", "repo", 999)

    assert exc_info.value.status_code == 404
    assert "Resource not found" in exc_info.value.message


@pytest.mark.asyncio
async def test_get_pull_request_rate_limit(github_client: GitHubClient, mocker: MockerFixture) -> None:
    """Verifies that a 403 with remaining=0 raises RateLimitExceededError."""
    mock_response = httpx.Response(
        status_code=403,
        headers={"x-ratelimit-remaining": "0", "x-ratelimit-reset": "1700000000"},
        json={"message": "API rate limit exceeded"},
        request=httpx.Request("GET", "https://api.github.com"),
    )
    mocker.patch("httpx.AsyncClient.get", return_value=mock_response)

    with pytest.raises(RateLimitExceededError):
        await github_client.get_pull_request("test", "repo", 1)


@pytest.mark.asyncio
async def test_diff_truncation_logic(test_settings: Settings, mocker: MockerFixture) -> None:
    """Verifies that diffs exceeding MAX_DIFF_LINES are cleanly truncated."""
    test_settings.MAX_DIFF_LINES = 10
    client = GitHubClient(settings=test_settings)

    mock_pr = {
        "title": "Large PR",
        "body": "",
        "state": "open",
        "base": {"ref": "main", "sha": "base123"},
        "head": {"ref": "feat", "sha": "head456"},
        "user": {"login": "bob"},
        "merged": False,
        "html_url": "https://github.com/test/repo/pull/2",
    }
    mock_files = [{"filename": "large.py", "status": "modified", "additions": 50, "deletions": 0}]
    # 25 lines of diff
    mock_diff_lines = [f"+ line {i}" for i in range(25)]
    mock_diff_text = "\n".join(mock_diff_lines)

    async def mock_get(self, url, *args, **kwargs):
        if url.endswith("/files"):
            return httpx.Response(200, json=mock_files, request=httpx.Request("GET", url))
        headers = kwargs.get("headers", {})
        if headers.get("Accept") == "application/vnd.github.v3.diff":
            return httpx.Response(200, text=mock_diff_text, request=httpx.Request("GET", url))
        return httpx.Response(200, json=mock_pr, request=httpx.Request("GET", url))

    mocker.patch("httpx.AsyncClient.get", new=mock_get)

    diff_data = await client.get_complete_pr_diff_data("test", "repo", 2)
    assert diff_data.is_truncated is True
    assert "[TRUNCATED DUE TO SIZE LIMITS]" in diff_data.raw_diff
    # Truncated diff must have 10 lines + notice
    assert len(diff_data.raw_diff.splitlines()) <= 13
