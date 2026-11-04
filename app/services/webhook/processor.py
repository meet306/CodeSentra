"""
GitHub Webhook Event Processor.
Parses PR events, enforces idempotency, triggers multi-agent reviews,
and delegates merged PRs to the learner service.
"""

from typing import Any

from app.config import Settings, get_settings
from app.core.logging import logger
from app.integrations.github_app import GitHubAppAuthManager
from app.schemas.review import ReviewRequest, ReviewResponse
from app.services.orchestrator.orchestrator_service import OrchestratorService
from app.services.reviewer.github_poster import GitHubReviewPoster


class WebhookProcessor:
    """Processes verified GitHub webhook events with idempotency and background dispatch."""

    def __init__(
        self,
        orchestrator: OrchestratorService | None = None,
        poster: GitHubReviewPoster | None = None,
        auth_manager: GitHubAppAuthManager | None = None,
        settings: Settings | None = None,
    ):
        self.settings = settings or get_settings()
        self.orchestrator = orchestrator or OrchestratorService(settings=self.settings)
        self.poster = poster or GitHubReviewPoster(settings=self.settings)
        self.auth_manager = auth_manager or GitHubAppAuthManager(settings=self.settings)

        # In-memory idempotency cache (delivery IDs & commit SHAs processed)
        self._processed_events: set[str] = set()

    def is_duplicate_event(self, event_key: str) -> bool:
        """Checks if an event delivery or PR commit SHA was already processed."""
        if event_key in self._processed_events:
            return True
        self._processed_events.add(event_key)
        # Cap set size to keep memory low
        if len(self._processed_events) > 5000:
            self._processed_events.clear()
        return False

    async def process_pull_request_event(
        self,
        payload: dict[str, Any],
        delivery_id: str | None = None,
    ) -> dict[str, Any]:
        """Main handler for 'pull_request' webhook events."""
        action = payload.get("action")
        pr_data = payload.get("pull_request", {})
        repo_data = payload.get("repository", {})

        repo_name = repo_data.get("name")
        repo_owner = repo_data.get("owner", {}).get("login")
        pr_number = pr_data.get("number")
        head_sha = pr_data.get("head", {}).get("sha", "")
        installation_id = payload.get("installation", {}).get("id")

        if not repo_name or not repo_owner or not pr_number:
            logger.warning("Incomplete webhook PR payload received.")
            return {"status": "ignored", "reason": "Missing repository or PR numbers."}

        # Idempotency check: combine delivery ID or repo+pr+head_sha
        idempotency_key = delivery_id or f"{repo_owner}/{repo_name}#{pr_number}:{head_sha}:{action}"
        if self.is_duplicate_event(idempotency_key):
            logger.info(f"Duplicate webhook event '{idempotency_key}' detected. Skipping.")
            return {"status": "skipped", "reason": "Idempotent event already processed."}

        logger.info(f"Processing webhook: PR {repo_owner}/{repo_name}#{pr_number} action '{action}'")

        # 1. Handle PR Opened, Synchronize (new commits pushed), or Reopened
        if action in ["opened", "synchronize", "reopened"]:
            # Retrieve installation token if GitHub App is installed
            auth_token = None
            if installation_id:
                try:
                    auth_token = await self.auth_manager.get_installation_access_token(installation_id)
                except Exception as e:
                    logger.warning(f"Could not acquire installation token: {e}. Falling back to default token.")

            # Trigger multi-agent review
            review_req = ReviewRequest(
                repo_owner=repo_owner,
                repo_name=repo_name,
                pr_number=pr_number,
                dry_run=self.settings.DRY_RUN,
            )

            review_res: ReviewResponse = await self.orchestrator.execute_multi_agent_review(review_req)

            # Post review findings to GitHub
            post_result = await self.poster.post_review(
                owner=repo_owner,
                repo=repo_name,
                pull_number=pr_number,
                review=review_res,
                auth_token=auth_token,
                commit_sha=head_sha,
            )

            return {
                "status": "reviewed",
                "action": action,
                "repo": f"{repo_owner}/{repo_name}",
                "pr_number": pr_number,
                "findings_count": review_res.summary.total_findings,
                "post_result": post_result,
            }

        # 2. Handle PR Merged (Closed with merged == True)
        elif action == "closed" and pr_data.get("merged", False):
            logger.info(f"PR {repo_owner}/{repo_name}#{pr_number} was merged. Extracting repository patterns.")
            from app.services.learner.learner_service import LearnerService
            learner = LearnerService(settings=self.settings)
            learned = await learner.learn_from_merged_pr(
                owner=repo_owner,
                repo=repo_name,
                pull_number=pr_number,
            )
            return {
                "status": "learning_triggered",
                "action": "merged",
                "repo": f"{repo_owner}/{repo_name}",
                "pr_number": pr_number,
                "patterns_learned": len(learned),
            }

        else:
            logger.info(f"Unhandled PR action '{action}'. Ignoring.")
            return {"status": "ignored", "action": action}
