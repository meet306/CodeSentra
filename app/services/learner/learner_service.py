"""
Self-Improving Learner Service.
Extracts approved repository patterns from merged PRs, collects developer feedback,
and supplies active learned conventions to future review agent prompts.
"""

from typing import Any

from sqlalchemy import select

from app.config import Settings, get_settings
from app.core.logging import logger
from app.database.models.developer_feedback import DeveloperFeedback
from app.database.models.organization import Organization
from app.database.models.pattern import RepositoryPattern
from app.database.models.repository import Repository
from app.database.session import get_session_factory
from app.integrations.github import GitHubClient
from app.integrations.groq import GroqClient

PATTERN_EXTRACTION_PROMPT = """You are CodeSentra's Pattern Learning Engine.
Your task is to analyze code changes from an APPROVED & MERGED Pull Request and extract
positive, repository-specific coding conventions, standards, or architectural patterns.

### GUIDELINES:
- ONLY extract clear, recurring conventions (e.g. typing conventions, specific exception handling style, logging conventions, dependency patterns).
- Do NOT assume every line of merged code is a convention.
- Ignore project-specific business logic; focus on transferable coding practices.
- Output between 0 and 3 high-quality patterns. If no obvious convention is established, return an empty list `[]`.

### JSON OUTPUT SCHEMA:
{
  "patterns": [
    {
      "category": "STYLE" | "ARCHITECTURE" | "SECURITY" | "ERROR_HANDLING",
      "rule_text": "Always use pydantic BaseModel with strict typing for API responses",
      "confidence": 0.85
    }
  ]
}
"""


class LearnerService:
    """Extracts, manages, and feeds repository-specific learned coding conventions."""

    def __init__(
        self,
        github_client: GitHubClient | None = None,
        groq_client: GroqClient | None = None,
        settings: Settings | None = None,
    ):
        self.settings = settings or get_settings()
        self.github_client = github_client or GitHubClient(self.settings)
        self.groq_client = groq_client or GroqClient(self.settings)
        self.session_factory = get_session_factory()

    async def get_active_patterns_for_repo(self, repo_full_name: str) -> list[str]:
        """Fetches confirmed active patterns for a repository to inject into AI reviews."""
        async with self.session_factory() as session:
            stmt = (
                select(RepositoryPattern.rule_text)
                .join(Repository, RepositoryPattern.repository_id == Repository.id)
                .where(
                    Repository.full_name == repo_full_name,
                    RepositoryPattern.is_active == True,  # noqa: E712
                    RepositoryPattern.confidence >= 0.7,
                )
                .order_by(RepositoryPattern.occurrences.desc())
                .limit(10)
            )
            result = await session.execute(stmt)
            patterns = [row[0] for row in result.fetchall()]
            return patterns

    async def learn_from_merged_pr(
        self,
        owner: str,
        repo: str,
        pull_number: int,
    ) -> list[dict[str, Any]]:
        """Analyzes a merged PR's diff to extract and persist coding patterns."""
        logger.info(f"Learner analyzing merged PR: {owner}/{repo}#{pull_number}")
        diff_data = await self.github_client.get_complete_pr_diff_data(owner, repo, pull_number)

        if not diff_data.files or not diff_data.raw_diff.strip():
            logger.info("Merged PR has empty diff, skipping pattern extraction.")
            return []

        user_content = f"""<pr_context>
Repository: {owner}/{repo}
Pull Request: #{pull_number} - {diff_data.pr_details.title}
</pr_context>

<merged_diff>
{diff_data.raw_diff[:3000]}
</merged_diff>

Extract positive coding conventions from this merged PR.
"""
        messages = [
            {"role": "system", "content": PATTERN_EXTRACTION_PROMPT},
            {"role": "user", "content": user_content},
        ]

        try:
            res = await self.groq_client.generate_completion_with_retry(messages=messages, temperature=0.1)
            extracted = res.get("data", {}).get("patterns", [])
        except Exception as e:
            logger.warning(f"Failed to extract patterns via Groq: {e}")
            return []

        if not isinstance(extracted, list) or not extracted:
            return []

        full_name = f"{owner}/{repo}"
        saved_patterns = []

        async with self.session_factory() as session:
            # Ensure repository exists
            repo_stmt = select(Repository).where(Repository.full_name == full_name)
            repo_res = await session.execute(repo_stmt)
            repo_obj = repo_res.scalar_one_or_none()

            if not repo_obj:
                org_stmt = select(Organization).where(Organization.slug == owner)
                org_res = await session.execute(org_stmt)
                org_obj = org_res.scalar_one_or_none()
                if not org_obj:
                    org_obj = Organization(name=owner, slug=owner)
                    session.add(org_obj)
                    await session.flush()

                repo_obj = Repository(
                    organization_id=org_obj.id,
                    owner=owner,
                    name=repo,
                    full_name=full_name,
                )
                session.add(repo_obj)
                await session.flush()

            for item in extracted:
                rule_text = str(item.get("rule_text", "")).strip()
                category = str(item.get("category", "STYLE")).upper()
                confidence = float(item.get("confidence", 0.8))

                if not rule_text:
                    continue

                # Check if similar rule already exists
                existing_stmt = select(RepositoryPattern).where(
                    RepositoryPattern.repository_id == repo_obj.id,
                    RepositoryPattern.rule_text == rule_text,
                )
                existing_res = await session.execute(existing_stmt)
                existing = existing_res.scalar_one_or_none()

                if existing:
                    existing.occurrences += 1
                    existing.confidence = min(1.0, existing.confidence + 0.05)
                else:
                    new_pattern = RepositoryPattern(
                        repository_id=repo_obj.id,
                        pattern_category=category,
                        rule_text=rule_text,
                        confidence=confidence,
                        occurrences=1,
                        is_active=True,
                    )
                    session.add(new_pattern)
                saved_patterns.append({"rule_text": rule_text, "category": category})

            await session.commit()
            logger.info(f"Learned and saved {len(saved_patterns)} patterns for repository {full_name}")

        return saved_patterns

    async def record_feedback(
        self,
        repo_full_name: str,
        feedback_type: str,
        finding_id: str | None = None,
        review_comment_id: str | None = None,
        comment: str | None = None,
    ) -> dict[str, Any]:
        """Records developer feedback on a finding or review comment."""
        async with self.session_factory() as session:
            repo_stmt = select(Repository).where(Repository.full_name == repo_full_name)
            res = await session.execute(repo_stmt)
            repo = res.scalar_one_or_none()

            if not repo:
                owner, name = repo_full_name.split("/", 1) if "/" in repo_full_name else ("default", repo_full_name)
                org = Organization(name=owner, slug=owner)
                session.add(org)
                await session.flush()
                repo = Repository(organization_id=org.id, owner=owner, name=name, full_name=repo_full_name)
                session.add(repo)
                await session.flush()

            fb = DeveloperFeedback(
                repository_id=repo.id,
                finding_id=finding_id,
                review_comment_id=review_comment_id,
                feedback_type=feedback_type.upper(),
                comment=comment,
            )
            session.add(fb)
            await session.commit()
            logger.info(f"Recorded developer feedback '{feedback_type}' for repo {repo_full_name}")

            return {"status": "recorded", "feedback_id": fb.id}
