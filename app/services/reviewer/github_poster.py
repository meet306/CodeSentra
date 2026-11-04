"""
GitHub PR Review Comment and Inline Feedback Posting Service.
Formats findings, posts top-level and inline reviews, and strictly enforces DRY_RUN mode.
"""

from typing import Any

import httpx

from app.config import Settings, get_settings
from app.core.errors import GitHubAPIError
from app.core.logging import logger
from app.schemas.review import ReviewResponse, Severity


class GitHubReviewPoster:
    """Formats and posts AI review feedback directly to GitHub Pull Requests."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    def format_review_markdown(self, review: ReviewResponse) -> str:
        """Formats a ReviewResponse into structured, professional GitHub markdown."""
        s = review.summary
        total = s.total_findings

        # Badges & header
        md = [
            "## 🤖 CodeSentra AI Pull Request Review\n",
            f"**Status**: Review Completed | **Total Findings**: {total} | **Execution Time**: {review.execution_time_seconds}s | **Model**: `{review.model_used}`\n",
            "| 🚨 Critical | ⚠️ High | 🟡 Medium | ℹ️ Low | 📝 Info |",
            "| :---: | :---: | :---: | :---: | :---: |",
            f"| {s.critical_count} | {s.high_count} | {s.medium_count} | {s.low_count} | {s.info_count} |\n",
            "### 📋 Overview\n",
            f"{s.overview}\n",
        ]

        if not review.findings:
            md.append("✅ **Clean Code**: No security vulnerabilities, bugs, or architectural anti-patterns found.\n")
            return "\n".join(md)

        md.append("### 🔍 Prioritized Findings\n")

        for idx, f in enumerate(review.findings, 1):
            severity_icon = {
                Severity.CRITICAL: "🚨 CRITICAL",
                Severity.HIGH: "⚠️ HIGH",
                Severity.MEDIUM: "🟡 MEDIUM",
                Severity.LOW: "ℹ️ LOW",
                Severity.INFO: "📝 INFO",
            }.get(f.severity, f.severity.value)

            loc_str = f"`{f.file_path}`" + (f":L{f.line_number}" if f.line_number else "")

            finding_block = [
                f"#### {idx}. [{severity_icon}] {f.title}",
                f"- **Location**: {loc_str}",
                f"- **Agent**: `{f.agent_name}` (Confidence: {int(f.confidence * 100)}%)",
                f"\n**Description**:\n{f.description}\n",
            ]

            if f.code_snippet:
                finding_block.append(f"**Observed Code**:\n```python\n{f.code_snippet.strip()}\n```\n")

            if f.suggested_fix:
                finding_block.append(f"**Suggested Fix**:\n```python\n{f.suggested_fix.strip()}\n```\n")

            finding_block.append(f"**Grounding Reasoning**:\n*{f.reasoning}*\n")
            finding_block.append("---\n")
            md.extend(finding_block)

        md.append("\n*Review generated autonomously by CodeSentra multi-agent code analysis system.*")
        return "\n".join(md)

    async def post_review(
        self,
        owner: str,
        repo: str,
        pull_number: int,
        review: ReviewResponse,
        auth_token: str | None = None,
        commit_sha: str | None = None,
    ) -> dict[str, Any]:
        """Posts structured review to GitHub or safely bypasses when in DRY_RUN mode."""
        is_dry_run = review.dry_run or self.settings.DRY_RUN

        body_markdown = self.format_review_markdown(review)

        if is_dry_run:
            logger.info(
                f"[DRY_RUN=True] Review for {owner}/{repo}#{pull_number} will NOT be posted to GitHub. "
                f"Generated {review.summary.total_findings} findings."
            )
            return {
                "posted": False,
                "dry_run": True,
                "review_id": None,
                "url": None,
                "message": "Dry run enabled. Review comment generated and validated but not published to GitHub.",
            }

        token = auth_token or self.settings.GITHUB_TOKEN
        if not token:
            raise GitHubAPIError("No GitHub authentication token available to post review.")

        url = f"{self.settings.GITHUB_API_BASE_URL.rstrip('/')}/repos/{owner}/{repo}/pulls/{pull_number}/reviews"
        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "CodeSentra-PR-Reviewer",
        }

        # Build inline comments where safe position is available
        comments_payload: list[dict[str, Any]] = []
        for f in review.findings:
            if f.line_number is not None and f.file_path:
                comment_body = (
                    f"**[{f.severity.value}] {f.title}**\n\n"
                    f"{f.description}\n\n"
                    f"**Suggested Fix**:\n```\n{f.suggested_fix or 'Review and refactor'}\n```"
                )
                comments_payload.append({
                    "path": f.file_path,
                    "line": f.line_number,
                    "body": comment_body,
                })

        payload: dict[str, Any] = {
            "body": body_markdown,
            "event": "COMMENT",  # STRICT: Never automatically APPROVE or REQUEST_CHANGES
        }
        if commit_sha:
            payload["commit_id"] = commit_sha
        if comments_payload:
            payload["comments"] = comments_payload[:10]  # Cap inline comments per review

        try:
            async with httpx.AsyncClient(timeout=25.0) as client:
                response = await client.post(url, headers=headers, json=payload)
                if response.is_error:
                    # Fallback to simple top-level PR comment if review creation fails (e.g. invalid commit SHA)
                    logger.warning(
                        f"Review creation failed with status {response.status_code}. Falling back to issue comment."
                    )
                    issue_url = f"{self.settings.GITHUB_API_BASE_URL.rstrip('/')}/repos/{owner}/{repo}/issues/{pull_number}/comments"
                    fallback_resp = await client.post(issue_url, headers=headers, json={"body": body_markdown})
                    if fallback_resp.is_error:
                        raise GitHubAPIError(
                            f"Failed to post fallback review comment: {fallback_resp.text[:200]}",
                            status_code=fallback_resp.status_code,
                        )
                    fb_data = fallback_resp.json()
                    return {
                        "posted": True,
                        "dry_run": False,
                        "comment_id": fb_data.get("id"),
                        "url": fb_data.get("html_url"),
                    }

                data = response.json()
                logger.info(f"Successfully posted PR review to {owner}/{repo}#{pull_number}: {data.get('html_url')}")
                return {
                    "posted": True,
                    "dry_run": False,
                    "review_id": data.get("id"),
                    "url": data.get("html_url"),
                }
        except httpx.RequestError as exc:
            logger.error(f"Network error posting review to GitHub: {exc}")
            raise GitHubAPIError(f"Network error posting review: {str(exc)}")
