"""
Pydantic models for code review findings, requests, and structured reviews.
"""

from enum import StrEnum

from pydantic import BaseModel, Field, field_validator


class Severity(StrEnum):
    """Vulnerability and issue severity ranking."""
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


class Finding(BaseModel):
    """Structured code review finding emitted by review agents."""
    agent_name: str = Field(description="Name of the reporting agent or 'static_reviewer' in Phase 1")
    title: str = Field(description="Concise description of the identified issue")
    description: str = Field(description="Detailed explanation of the issue and why it matters")
    severity: Severity = Field(description="Severity classification")
    confidence: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="Confidence score between 0.0 and 1.0",
    )
    file_path: str = Field(description="Path to the file where the issue was observed")
    line_number: int | None = Field(
        default=None,
        description="Exact diff line number if verifiable; None if safe position is unavailable",
    )
    code_snippet: str | None = Field(
        default=None,
        description="Exact code fragment from the diff illustrating the issue",
    )
    suggested_fix: str | None = Field(
        default=None,
        description="Actionable code change or guidance to resolve the finding",
    )
    reasoning: str = Field(
        description="Grounding reasoning explaining how the PR diff confirms this issue",
    )

    @field_validator("confidence")
    @classmethod
    def validate_confidence(cls, v: float) -> float:
        return round(float(v), 2)


class ReviewSummary(BaseModel):
    """Summary metrics and overview of findings."""
    total_findings: int = 0
    critical_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0
    info_count: int = 0
    overview: str = Field(description="High-level markdown synthesis of the PR changes and review outcome")


class ReviewRequest(BaseModel):
    """Request payload to initiate a PR code review."""
    repo_owner: str = Field(..., description="Repository owner (e.g. 'octocat' or organization)")
    repo_name: str = Field(..., description="Repository name (e.g. 'Hello-World')")
    pr_number: int = Field(..., ge=1, description="GitHub Pull Request number")
    dry_run: bool | None = Field(
        default=None,
        description="Override global DRY_RUN setting. If true, review is returned but not posted to GitHub.",
    )


class ReviewResponse(BaseModel):
    """Full code review response returned to client."""
    repo: str
    pr_number: int
    title: str
    author: str
    status: str = "completed"
    dry_run: bool
    summary: ReviewSummary
    findings: list[Finding] = Field(default_factory=list)
    execution_time_seconds: float
    model_used: str
    tokens_consumed: dict[str, int] | None = None
