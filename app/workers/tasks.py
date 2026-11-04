"""
Celery background tasks for PR review and repository convention learning.
"""

import asyncio
from typing import Any

from celery import shared_task

from app.config import get_settings
from app.core.errors import GitHubAPIError, RateLimitExceededError
from app.core.logging import logger
from app.database.models.finding import AgentFinding
from app.database.models.pull_request import PullRequest
from app.database.models.repository import Repository
from app.database.models.review_comment import ReviewComment
from app.database.models.review_session import ReviewSession
from app.database.session import get_session_factory
from app.schemas.review import ReviewRequest, ReviewResponse
from app.services.orchestrator.orchestrator_service import OrchestratorService
from app.services.reviewer.github_poster import GitHubReviewPoster


async def _execute_and_persist_review(
    repo_owner: str,
    repo_name: str,
    pr_number: int,
    dry_run: bool,
    auth_token: str | None = None,
    commit_sha: str | None = None,
) -> dict[str, Any]:
    """Asynchronous core logic executing review, saving to database, and posting to GitHub."""
    settings = get_settings()
    orchestrator = OrchestratorService(settings=settings)
    poster = GitHubReviewPoster(settings=settings)
    session_factory = get_session_factory()

    req = ReviewRequest(
        repo_owner=repo_owner,
        repo_name=repo_name,
        pr_number=pr_number,
        dry_run=dry_run,
    )

    review: ReviewResponse = await orchestrator.execute_multi_agent_review(req)

    # 1. Post to GitHub (respecting DRY_RUN)
    post_res = await poster.post_review(
        owner=repo_owner,
        repo=repo_name,
        pull_number=pr_number,
        review=review,
        auth_token=auth_token,
        commit_sha=commit_sha,
    )

    # 2. Persist to PostgreSQL / SQLite
    async with session_factory() as db:
        # Find or create repository
        full_name = f"{repo_owner}/{repo_name}"
        from sqlalchemy import select
        repo_stmt = select(Repository).where(Repository.full_name == full_name)
        result = await db.execute(repo_stmt)
        repo_obj = result.scalar_one_or_none()

        if not repo_obj:
            from app.database.models.organization import Organization
            # Create default organization if needed
            org_stmt = select(Organization).where(Organization.slug == repo_owner)
            org_res = await db.execute(org_stmt)
            org_obj = org_res.scalar_one_or_none()
            if not org_obj:
                org_obj = Organization(name=repo_owner, slug=repo_owner)
                db.add(org_obj)
                await db.flush()

            repo_obj = Repository(
                organization_id=org_obj.id,
                owner=repo_owner,
                name=repo_name,
                full_name=full_name,
            )
            db.add(repo_obj)
            await db.flush()

        # Find or create PR record
        pr_stmt = select(PullRequest).where(
            PullRequest.repository_id == repo_obj.id,
            PullRequest.pull_number == pr_number,
        )
        pr_res = await db.execute(pr_stmt)
        pr_obj = pr_res.scalar_one_or_none()
        if not pr_obj:
            pr_obj = PullRequest(
                repository_id=repo_obj.id,
                pull_number=pr_number,
                title=review.title,
                author=review.author,
                base_ref="main",
                head_ref="unknown",
                head_sha=commit_sha or "unknown",
            )
            db.add(pr_obj)
            await db.flush()

        # Create ReviewSession
        session_obj = ReviewSession(
            pull_request_id=pr_obj.id,
            status="completed",
            execution_time_seconds=review.execution_time_seconds,
            model_used=review.model_used,
            prompt_tokens=review.tokens_consumed.get("prompt_tokens", 0) if review.tokens_consumed else 0,
            completion_tokens=review.tokens_consumed.get("completion_tokens", 0) if review.tokens_consumed else 0,
            total_tokens=review.tokens_consumed.get("total_tokens", 0) if review.tokens_consumed else 0,
            overview=review.summary.overview,
            dry_run=review.dry_run,
        )
        db.add(session_obj)
        await db.flush()

        # Persist Findings
        for f in review.findings:
            finding_obj = AgentFinding(
                review_session_id=session_obj.id,
                agent_name=f.agent_name,
                title=f.title,
                description=f.description,
                severity=f.severity.value,
                confidence=f.confidence,
                file_path=f.file_path,
                line_number=f.line_number,
                code_snippet=f.code_snippet,
                suggested_fix=f.suggested_fix,
                reasoning=f.reasoning,
            )
            db.add(finding_obj)

        # Persist ReviewComment
        if post_res.get("posted"):
            comment_obj = ReviewComment(
                review_session_id=session_obj.id,
                github_review_id=str(post_res.get("review_id", "")),
                github_url=post_res.get("url"),
                comment_type="PR_REVIEW",
                body=poster.format_review_markdown(review),
            )
            db.add(comment_obj)

        await db.commit()
        logger.info(f"Persisted review session {session_obj.id} with {len(review.findings)} findings.")

    return {
        "status": "success",
        "findings_count": len(review.findings),
        "post_result": post_res,
    }


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=10,
    autoretry_for=(RateLimitExceededError, GitHubAPIError),
    retry_backoff=True,
    retry_backoff_max=120,
)
def review_pr_async_task(
    self,
    repo_owner: str,
    repo_name: str,
    pr_number: int,
    dry_run: bool = True,
    auth_token: str | None = None,
    commit_sha: str | None = None,
) -> dict[str, Any]:
    """Celery background worker task for full PR review pipeline."""
    logger.info(f"Celery executing PR review task: {repo_owner}/{repo_name}#{pr_number}")
    return asyncio.run(
        _execute_and_persist_review(
            repo_owner=repo_owner,
            repo_name=repo_name,
            pr_number=pr_number,
            dry_run=dry_run,
            auth_token=auth_token,
            commit_sha=commit_sha,
        )
    )
