"""
Orchestrator Service.
Coordinates LangGraph multi-agent execution, loads PR context and learned patterns,
and produces the consolidated ReviewResponse.
"""

import time

from app.config import Settings, get_settings
from app.core.logging import logger
from app.graph.nodes import ReviewGraphNodes
from app.graph.state import ReviewGraphState
from app.graph.workflow import create_review_graph
from app.integrations.github import GitHubClient
from app.integrations.groq import GroqClient
from app.schemas.review import (
    ReviewRequest,
    ReviewResponse,
    ReviewSummary,
    Severity,
)


class OrchestratorService:
    """Central workflow engine coordinating multi-agent LangGraph execution."""

    def __init__(
        self,
        github_client: GitHubClient | None = None,
        groq_client: GroqClient | None = None,
        settings: Settings | None = None,
    ):
        self.settings = settings or get_settings()
        self.github_client = github_client or GitHubClient(self.settings)
        self.groq_client = groq_client or GroqClient(self.settings)
        self.nodes = ReviewGraphNodes(groq_client=self.groq_client)
        self.graph = create_review_graph(self.nodes)

    async def execute_multi_agent_review(
        self,
        request: ReviewRequest,
        learned_patterns: list[str] | None = None,
    ) -> ReviewResponse:
        """Runs the complete multi-agent code review workflow."""
        start_time = time.time()
        dry_run = request.dry_run if request.dry_run is not None else self.settings.DRY_RUN

        logger.info(
            f"Orchestrating multi-agent review for {request.repo_owner}/{request.repo_name}#{request.pr_number}"
        )

        # 1. Fetch complete PR diff and changed files from GitHub
        diff_data = await self.github_client.get_complete_pr_diff_data(
            owner=request.repo_owner,
            repo=request.repo_name,
            pull_number=request.pr_number,
        )

        # 2. Check for empty diff
        if not diff_data.files or not diff_data.raw_diff.strip():
            logger.info("PR diff is empty, skipping multi-agent graph.")
            execution_time = round(time.time() - start_time, 2)
            return ReviewResponse(
                repo=f"{request.repo_owner}/{request.repo_name}",
                pr_number=request.pr_number,
                title=diff_data.pr_details.title,
                author=diff_data.pr_details.author,
                status="completed",
                dry_run=dry_run,
                summary=ReviewSummary(
                    total_findings=0,
                    overview="No file changes found in this Pull Request.",
                ),
                findings=[],
                execution_time_seconds=execution_time,
                model_used=self.settings.GROQ_MODEL,
            )

        # 3. Setup initial LangGraph state
        patterns_to_use = learned_patterns
        if patterns_to_use is None:
            try:
                from app.services.learner.learner_service import LearnerService
                learner = LearnerService(settings=self.settings)
                patterns_to_use = await learner.get_active_patterns_for_repo(f"{request.repo_owner}/{request.repo_name}")
                if patterns_to_use:
                    logger.info(f"Loaded {len(patterns_to_use)} learned repo conventions for review.")
            except Exception as e:
                logger.warning(f"Could not load learned patterns: {e}")
                patterns_to_use = []

        initial_state: ReviewGraphState = {
            "repo_owner": request.repo_owner,
            "repo_name": request.repo_name,
            "pr_number": request.pr_number,
            "diff_data": diff_data,
            "learned_patterns": patterns_to_use or [],
            "static_findings": [],
            "security_findings": [],
            "architecture_findings": [],
            "style_findings": [],
            "consolidated_findings": [],
            "overview": "",
            "errors": [],
        }

        # 4. Invoke LangGraph workflow
        final_state: ReviewGraphState = await self.graph.ainvoke(initial_state)

        consolidated = final_state.get("consolidated_findings", [])
        overview = final_state.get("overview", "Multi-agent code review completed.")

        # 5. Calculate summary metrics
        severity_counts = {
            Severity.CRITICAL: 0,
            Severity.HIGH: 0,
            Severity.MEDIUM: 0,
            Severity.LOW: 0,
            Severity.INFO: 0,
        }
        for f in consolidated:
            severity_counts[f.severity] = severity_counts.get(f.severity, 0) + 1

        summary = ReviewSummary(
            total_findings=len(consolidated),
            critical_count=severity_counts[Severity.CRITICAL],
            high_count=severity_counts[Severity.HIGH],
            medium_count=severity_counts[Severity.MEDIUM],
            low_count=severity_counts[Severity.LOW],
            info_count=severity_counts[Severity.INFO],
            overview=overview,
        )

        execution_time = round(time.time() - start_time, 2)
        logger.info(
            f"Completed multi-agent review: {len(consolidated)} consolidated findings in {execution_time}s"
        )

        return ReviewResponse(
            repo=f"{request.repo_owner}/{request.repo_name}",
            pr_number=request.pr_number,
            title=diff_data.pr_details.title,
            author=diff_data.pr_details.author,
            status="completed",
            dry_run=dry_run,
            summary=summary,
            findings=consolidated,
            execution_time_seconds=execution_time,
            model_used=self.settings.GROQ_MODEL,
        )
