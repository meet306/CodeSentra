"""
Pydantic models representing GitHub PR entities, changed files, and diff structures.
"""


from pydantic import BaseModel, Field


class PRFileChange(BaseModel):
    """Represents a changed file within a Pull Request."""
    filename: str = Field(description="Relative path of the changed file")
    status: str = Field(description="Change status (e.g. added, modified, removed)")
    additions: int = Field(default=0, description="Lines added")
    deletions: int = Field(default=0, description="Lines deleted")
    changes: int = Field(default=0, description="Total changed lines")
    patch: str | None = Field(default=None, description="Unified diff patch for this file")
    raw_url: str | None = Field(default=None, description="URL to raw file content")
    sha: str | None = Field(default=None, description="Blob SHA")


class PRDetails(BaseModel):
    """Metadata and status of a GitHub Pull Request."""
    owner: str = Field(description="Repository owner / organization")
    repo: str = Field(description="Repository name")
    pull_number: int = Field(description="Pull request number")
    title: str = Field(description="PR title")
    body: str | None = Field(default="", description="PR description body")
    state: str = Field(default="open", description="PR state: open, closed")
    base_ref: str = Field(description="Target branch name")
    head_ref: str = Field(description="Source branch name")
    base_sha: str = Field(description="Target commit SHA")
    head_sha: str = Field(description="Source commit SHA")
    author: str = Field(description="GitHub username of the PR author")
    is_merged: bool = Field(default=False, description="Whether the PR has been merged")
    html_url: str = Field(description="Web URL of the Pull Request")
    diff_url: str | None = Field(default=None, description="URL to raw diff")


class PRDiffData(BaseModel):
    """Aggregated diff and file change information for a Pull Request."""
    pr_details: PRDetails
    files: list[PRFileChange] = Field(default_factory=list)
    raw_diff: str = Field(default="", description="Full or truncated unified diff text")
    total_files: int = 0
    total_additions: int = 0
    total_deletions: int = 0
    is_truncated: bool = Field(default=False, description="True if diff was truncated to protect token/memory limits")
