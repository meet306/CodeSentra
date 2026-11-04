"""
Base Review Agent providing shared prompt formatting, defensive delimiters,
and structured Groq inference with schema validation.
"""

from typing import Any

from app.config import Settings, get_settings
from app.core.logging import logger
from app.integrations.groq import GroqClient
from app.schemas.github import PRDiffData
from app.schemas.review import Finding


class BaseReviewAgent:
    """Abstract base class for all specialized code review agents."""

    def __init__(
        self,
        agent_name: str,
        system_prompt: str,
        groq_client: GroqClient | None = None,
        settings: Settings | None = None,
    ):
        self.agent_name = agent_name
        self.system_prompt = system_prompt
        self.settings = settings or get_settings()
        self.groq_client = groq_client or GroqClient(self.settings)

    def _build_agent_prompt(
        self,
        diff_data: PRDiffData,
        learned_patterns: list[str] | None = None,
    ) -> str:
        """Constructs safe delimited prompt containing PR metadata, learned patterns, and diff."""
        pr = diff_data.pr_details
        changed_files_list = "\n".join(
            [f"- {f.filename} (+{f.additions}, -{f.deletions})" for f in diff_data.files]
        )

        patterns_section = ""
        if learned_patterns:
            formatted_patterns = "\n".join([f"- {p}" for p in learned_patterns])
            patterns_section = f"\n<learned_conventions>\n{formatted_patterns}\n</learned_conventions>\n"

        prompt = f"""<pr_context>
Repository: {pr.owner}/{pr.repo}
Pull Request: #{pr.pull_number} - {pr.title}
Author: {pr.author}
Target Branch: {pr.base_ref} <- Source Branch: {pr.head_ref}
Description:
{pr.body if pr.body else '(No description provided)'}

Changed Files ({diff_data.total_files} files, +{diff_data.total_additions} / -{diff_data.total_deletions} lines):
{changed_files_list}
</pr_context>
{patterns_section}
<untrusted_diff>
{diff_data.raw_diff}
</untrusted_diff>

Analyze the diff according to your specialized agent instructions and return structured JSON findings.
"""
        return prompt

    async def analyze(
        self,
        diff_data: PRDiffData,
        learned_patterns: list[str] | None = None,
    ) -> list[Finding]:
        """Executes LLM inference for this specialized agent and parses valid findings."""
        if not diff_data.files or not diff_data.raw_diff.strip():
            logger.info(f"Agent '{self.agent_name}': PR diff is empty, skipping.")
            return []

        user_content = self._build_agent_prompt(diff_data, learned_patterns)
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_content},
        ]

        valid_files = [f.filename for f in diff_data.files]

        try:
            logger.info(f"Executing agent '{self.agent_name}' review...")
            result = await self.groq_client.generate_completion_with_retry(
                messages=messages,
                model=self.settings.GROQ_MODEL,
                temperature=0.1,
            )
            data: dict[str, Any] = result.get("data", {})
            findings = self.groq_client.parse_findings_from_dict(
                raw_data=data,
                agent_name=self.agent_name,
                valid_files=valid_files,
            )
            logger.info(f"Agent '{self.agent_name}' generated {len(findings)} findings.")
            return findings
        except Exception as e:
            logger.error(f"Error during agent '{self.agent_name}' execution: {e}")
            # Fault isolation: an individual agent failure does not bring down the entire review pipeline
            return []
