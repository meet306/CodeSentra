"""
LangGraph review workflow state schema.
"""

from typing import TypedDict

from app.schemas.github import PRDiffData
from app.schemas.review import Finding


class ReviewGraphState(TypedDict, total=False):
    """Execution state passed through the LangGraph multi-agent review graph."""

    repo_owner: str
    repo_name: str
    pr_number: int
    diff_data: PRDiffData | None
    learned_patterns: list[str]

    # Individual Agent Findings
    static_findings: list[Finding]
    security_findings: list[Finding]
    architecture_findings: list[Finding]
    style_findings: list[Finding]

    # Consolidated Results
    consolidated_findings: list[Finding]
    overview: str
    errors: list[str]
