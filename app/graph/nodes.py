"""
LangGraph execution nodes for multi-agent code review.
"""


from app.agents.architecture_agent import ArchitectureAgent
from app.agents.security_agent import SecurityAgent
from app.agents.static_agent import StaticAnalysisAgent
from app.agents.style_agent import CodeStyleAgent
from app.config import get_settings
from app.core.logging import logger
from app.graph.state import ReviewGraphState
from app.integrations.groq import GroqClient
from app.schemas.review import Finding, Severity
from app.services.orchestrator.merger import FindingMerger


class ReviewGraphNodes:
    """Encapsulates node execution methods with shared clients and merger."""

    def __init__(self, groq_client: GroqClient | None = None):
        self.settings = get_settings()
        self.groq_client = groq_client or GroqClient(self.settings)
        self.merger = FindingMerger()

        # Instantiate the 4 specialized agents
        self.static_agent = StaticAnalysisAgent(groq_client=self.groq_client, settings=self.settings)
        self.security_agent = SecurityAgent(groq_client=self.groq_client, settings=self.settings)
        self.architecture_agent = ArchitectureAgent(groq_client=self.groq_client, settings=self.settings)
        self.style_agent = CodeStyleAgent(groq_client=self.groq_client, settings=self.settings)

    async def static_analysis_node(self, state: ReviewGraphState) -> dict[str, list[Finding]]:
        """Node executing static code analysis and bug detection."""
        diff_data = state.get("diff_data")
        if not diff_data:
            return {"static_findings": []}
        findings = await self.static_agent.analyze(diff_data=diff_data)
        return {"static_findings": findings}

    async def security_review_node(self, state: ReviewGraphState) -> dict[str, list[Finding]]:
        """Node executing OWASP and security vulnerability assessment."""
        diff_data = state.get("diff_data")
        if not diff_data:
            return {"security_findings": []}
        findings = await self.security_agent.analyze(diff_data=diff_data)
        return {"security_findings": findings}

    async def architecture_review_node(self, state: ReviewGraphState) -> dict[str, list[Finding]]:
        """Node evaluating architecture, coupling, and design patterns."""
        diff_data = state.get("diff_data")
        if not diff_data:
            return {"architecture_findings": []}
        findings = await self.architecture_agent.analyze(diff_data=diff_data)
        return {"architecture_findings": findings}

    async def style_review_node(self, state: ReviewGraphState) -> dict[str, list[Finding]]:
        """Node reviewing style, naming conventions, and learned repo rules."""
        diff_data = state.get("diff_data")
        if not diff_data:
            return {"style_findings": []}
        learned_patterns = state.get("learned_patterns", [])
        findings = await self.style_agent.analyze(diff_data=diff_data, learned_patterns=learned_patterns)
        return {"style_findings": findings}

    async def merge_findings_node(self, state: ReviewGraphState) -> dict[str, list[Finding]]:
        """Node deduplicating, combining, and ranking all agent findings."""
        agent_map: dict[str, list[Finding]] = {
            "static_analysis": state.get("static_findings", []),
            "security": state.get("security_findings", []),
            "architecture": state.get("architecture_findings", []),
            "style": state.get("style_findings", []),
        }
        consolidated = self.merger.merge(agent_map)
        return {"consolidated_findings": consolidated}

    async def synthesize_review_node(self, state: ReviewGraphState) -> dict[str, str]:
        """Node generating high-level summary overview markdown."""
        findings = state.get("consolidated_findings", [])
        diff_data = state.get("diff_data")

        pr_title = diff_data.pr_details.title if diff_data else "Pull Request"
        total_files = diff_data.total_files if diff_data else 0

        severity_counts = {
            Severity.CRITICAL: sum(1 for f in findings if f.severity == Severity.CRITICAL),
            Severity.HIGH: sum(1 for f in findings if f.severity == Severity.HIGH),
            Severity.MEDIUM: sum(1 for f in findings if f.severity == Severity.MEDIUM),
            Severity.LOW: sum(1 for f in findings if f.severity == Severity.LOW),
            Severity.INFO: sum(1 for f in findings if f.severity == Severity.INFO),
        }

        if not findings:
            overview = (
                f"### CodeSentra Multi-Agent Review Summary\n\n"
                f"The review examined **{total_files} changed files** in PR *\"{pr_title}\"* "
                f"across 4 specialized AI agents (Static Analysis, Security, Architecture, Style). "
                f"No bugs, vulnerabilities, or maintainability concerns were identified. The changes appear clean and ready."
            )
        else:
            overview = (
                f"### CodeSentra Multi-Agent Review Summary\n\n"
                f"Completed multi-agent review across **{total_files} files** in PR *\"{pr_title}\"*.\n\n"
                f"**Findings Distribution:**\n"
                f"- **Critical**: {severity_counts[Severity.CRITICAL]}\n"
                f"- **High**: {severity_counts[Severity.HIGH]}\n"
                f"- **Medium**: {severity_counts[Severity.MEDIUM]}\n"
                f"- **Low**: {severity_counts[Severity.LOW]}\n"
                f"- **Info**: {severity_counts[Severity.INFO]}\n\n"
                f"Please review the detailed findings and suggested fixes prioritized above."
            )

        logger.info("Synthesized review summary markdown.")
        return {"overview": overview}
