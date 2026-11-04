"""
Pytest fixtures and test configurations for CodeSentra.
"""

from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import Settings
from app.main import create_application
from app.schemas.github import PRDetails, PRDiffData, PRFileChange
from app.schemas.review import Finding, Severity


@pytest.fixture
def test_settings() -> Settings:
    """Fixture providing test-specific application settings."""
    return Settings(
        ENVIRONMENT="test",
        LOG_LEVEL="DEBUG",
        GROQ_API_KEY="gsk_test_mock_groq_api_key_123456789012345",
        GROQ_MODEL="llama-3.3-70b-versatile",
        GITHUB_TOKEN="ghp_test_mock_github_token_123456789012345",
        DRY_RUN=True,
    )


@pytest.fixture
def sample_pr_details() -> PRDetails:
    """Sample Pull Request metadata."""
    return PRDetails(
        owner="octocat",
        repo="Hello-World",
        pull_number=42,
        title="Add user authentication and database models",
        body="This PR implements basic auth and user registration.",
        state="open",
        base_ref="main",
        head_ref="feature/auth",
        base_sha="6dcb09b5b57875f334f61aebed695e2e4193db5e",
        head_sha="7fd1a60b01f91b314f59955a4e4d4e80d8edf11d",
        author="monalisa",
        is_merged=False,
        html_url="https://github.com/octocat/Hello-World/pull/42",
        diff_url="https://github.com/octocat/Hello-World/pull/42.diff",
    )


@pytest.fixture
def sample_file_changes() -> list[PRFileChange]:
    """Sample changed files within a PR."""
    return [
        PRFileChange(
            filename="src/auth.py",
            status="modified",
            additions=15,
            deletions=2,
            changes=17,
            patch="@@ -1,5 +1,18 @@\n+import hashlib\n+def hash_password(password):\n+    return hashlib.md5(password.encode()).hexdigest()\n",
            raw_url="https://github.com/octocat/Hello-World/raw/src/auth.py",
            sha="abcdef1234567890",
        )
    ]


@pytest.fixture
def sample_diff_data(sample_pr_details: PRDetails, sample_file_changes: list[PRFileChange]) -> PRDiffData:
    """Aggregated sample PR diff dataset."""
    diff_text = """diff --git a/src/auth.py b/src/auth.py
index e69de29..d95f3ad 100644
--- a/src/auth.py
+++ b/src/auth.py
@@ -1,5 +1,18 @@
+import hashlib
+
+def hash_password(password: str) -> str:
+    # INSECURE: MD5 used for password hashing
+    return hashlib.md5(password.encode()).hexdigest()
"""
    return PRDiffData(
        pr_details=sample_pr_details,
        files=sample_file_changes,
        raw_diff=diff_text,
        total_files=1,
        total_additions=15,
        total_deletions=2,
        is_truncated=False,
    )


@pytest.fixture
def sample_finding() -> Finding:
    """Sample structured review finding."""
    return Finding(
        agent_name="phase1_ai_reviewer",
        title="Insecure MD5 password hashing",
        description="The MD5 hashing algorithm is cryptographically broken and vulnerable to collision and pre-image attacks.",
        severity=Severity.HIGH,
        confidence=0.95,
        file_path="src/auth.py",
        line_number=5,
        code_snippet="return hashlib.md5(password.encode()).hexdigest()",
        suggested_fix="Use a secure password hashing algorithm such as Argon2id or bcrypt.",
        reasoning="MD5 algorithm is used on password input without salt or work factor.",
    )


@pytest.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """Asynchronous HTTP test client for FastAPI."""
    app = create_application()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
