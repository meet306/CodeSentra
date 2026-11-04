"""
GitHub REST API integration client.
Fetches Pull Request metadata, changed files, and unified diffs.
"""

from typing import Any

import httpx

from app.config import Settings, get_settings
from app.core.errors import GitHubAPIError, RateLimitExceededError
from app.core.logging import logger
from app.schemas.github import PRDetails, PRDiffData, PRFileChange


class GitHubClient:
    """Asynchronous client for interacting with the GitHub REST API."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.base_url = self.settings.GITHUB_API_BASE_URL.rstrip("/")
        self.headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "CodeSentra-PR-Reviewer/0.1.0",
        }
        if self.settings.GITHUB_TOKEN:
            self.headers["Authorization"] = f"Bearer {self.settings.GITHUB_TOKEN}"

    def _handle_response_status(self, response: httpx.Response, action_description: str) -> None:
        """Inspects HTTP status code and raises domain errors if needed."""
        if response.status_code == 401:
            raise GitHubAPIError("Invalid or missing GitHub authentication token.", status_code=401)
        elif response.status_code == 403:
            remaining = response.headers.get("x-ratelimit-remaining", "0")
            if remaining == "0":
                reset_time = response.headers.get("x-ratelimit-reset", "unknown")
                raise RateLimitExceededError(
                    f"GitHub API rate limit exceeded. Resets at unix timestamp: {reset_time}",
                    details={"reset": reset_time},
                )
            raise GitHubAPIError("Forbidden access to GitHub resource. Check token permissions.", status_code=403)
        elif response.status_code == 404:
            raise GitHubAPIError(f"Resource not found on GitHub during {action_description}.", status_code=404)
        elif response.is_error:
            raise GitHubAPIError(
                f"GitHub API request failed during {action_description} with status {response.status_code}: {response.text[:200]}",
                status_code=response.status_code,
            )

    async def get_pull_request(self, owner: str, repo: str, pull_number: int) -> PRDetails:
        """Fetches metadata for a single pull request."""
        url = f"{self.base_url}/repos/{owner}/{repo}/pulls/{pull_number}"
        logger.info(f"Fetching PR metadata: {owner}/{repo}#{pull_number}")

        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.get(url, headers=self.headers)
                self._handle_response_status(response, f"fetching PR metadata for {owner}/{repo}#{pull_number}")
                data = response.json()

                return PRDetails(
                    owner=owner,
                    repo=repo,
                    pull_number=pull_number,
                    title=data.get("title", "Untitled PR"),
                    body=data.get("body") or "",
                    state=data.get("state", "open"),
                    base_ref=data.get("base", {}).get("ref", "main"),
                    head_ref=data.get("head", {}).get("ref", "unknown"),
                    base_sha=data.get("base", {}).get("sha", ""),
                    head_sha=data.get("head", {}).get("sha", ""),
                    author=data.get("user", {}).get("login", "unknown"),
                    is_merged=data.get("merged", False),
                    html_url=data.get("html_url", ""),
                    diff_url=data.get("diff_url"),
                )
        except httpx.RequestError as exc:
            logger.error(f"Network error contacting GitHub API: {exc}")
            raise GitHubAPIError(f"Network error connecting to GitHub: {str(exc)}")

    async def get_pr_files(self, owner: str, repo: str, pull_number: int) -> list[PRFileChange]:
        """Fetches list of changed files with diff patches."""
        url = f"{self.base_url}/repos/{owner}/{repo}/pulls/{pull_number}/files"
        params = {"per_page": min(self.settings.MAX_DIFF_FILES, 100)}
        logger.info(f"Fetching PR files: {owner}/{repo}#{pull_number}")

        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.get(url, headers=self.headers, params=params)
                self._handle_response_status(response, f"fetching PR files for {owner}/{repo}#{pull_number}")
                files_json: list[dict[str, Any]] = response.json()

                file_changes: list[PRFileChange] = []
                for item in files_json[:self.settings.MAX_DIFF_FILES]:
                    file_changes.append(
                        PRFileChange(
                            filename=item.get("filename", ""),
                            status=item.get("status", "modified"),
                            additions=item.get("additions", 0),
                            deletions=item.get("deletions", 0),
                            changes=item.get("changes", 0),
                            patch=item.get("patch"),
                            raw_url=item.get("raw_url"),
                            sha=item.get("sha"),
                        )
                    )
                return file_changes
        except httpx.RequestError as exc:
            logger.error(f"Network error fetching PR files: {exc}")
            raise GitHubAPIError(f"Network error connecting to GitHub: {str(exc)}")

    async def get_raw_diff(self, owner: str, repo: str, pull_number: int) -> str:
        """Fetches the raw unified diff for the PR."""
        url = f"{self.base_url}/repos/{owner}/{repo}/pulls/{pull_number}"
        diff_headers = dict(self.headers)
        diff_headers["Accept"] = "application/vnd.github.v3.diff"

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, headers=diff_headers)
                self._handle_response_status(response, f"fetching PR diff for {owner}/{repo}#{pull_number}")
                return response.text
        except httpx.RequestError as exc:
            logger.error(f"Network error fetching raw diff: {exc}")
            raise GitHubAPIError(f"Network error connecting to GitHub: {str(exc)}")

    async def get_complete_pr_diff_data(self, owner: str, repo: str, pull_number: int) -> PRDiffData:
        """Fetches PR metadata, changed files, and unified diff with budget-safe truncation."""
        pr_details = await self.get_pull_request(owner, repo, pull_number)
        files = await self.get_pr_files(owner, repo, pull_number)
        raw_diff = await self.get_raw_diff(owner, repo, pull_number)

        # Calculate totals
        total_additions = sum(f.additions for f in files)
        total_deletions = sum(f.deletions for f in files)

        # Truncate diff if lines exceed MAX_DIFF_LINES
        diff_lines = raw_diff.splitlines()
        is_truncated = False
        if len(diff_lines) > self.settings.MAX_DIFF_LINES:
            logger.warning(
                f"Diff length ({len(diff_lines)} lines) exceeds maximum limit ({self.settings.MAX_DIFF_LINES}). Truncating to avoid Groq token overflow."
            )
            raw_diff = "\n".join(diff_lines[:self.settings.MAX_DIFF_LINES]) + "\n\n... [TRUNCATED DUE TO SIZE LIMITS] ..."
            is_truncated = True

        return PRDiffData(
            pr_details=pr_details,
            files=files,
            raw_diff=raw_diff,
            total_files=len(files),
            total_additions=total_additions,
            total_deletions=total_deletions,
            is_truncated=is_truncated,
        )
