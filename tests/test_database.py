"""
Unit tests for database models, async session, and persistence.
"""

import uuid

import pytest
from sqlalchemy import select

from app.database.models import (
    AgentFinding,
    Organization,
    PullRequest,
    Repository,
    ReviewSession,
)
from app.database.session import get_session_factory, init_db


@pytest.mark.asyncio
async def test_database_initialization_and_models() -> None:
    """Verifies that database schema initializes and models persist with relationships."""
    await init_db()

    uid = uuid.uuid4().hex[:8]
    session_factory = get_session_factory()
    async with session_factory() as session:
        # Create Organization with unique slug
        org = Organization(name=f"Test Org {uid}", slug=f"test-org-{uid}")
        session.add(org)
        await session.flush()

        # Create Repository under Organization
        repo = Repository(
            organization_id=org.id,
            owner=f"test-org-{uid}",
            name="test-repo",
            full_name=f"test-org-{uid}/test-repo",
            is_private=False,
        )
        session.add(repo)
        await session.flush()

        # Create Pull Request
        pr = PullRequest(
            repository_id=repo.id,
            pull_number=1,
            title="Implement database",
            author="dev",
            base_ref="main",
            head_ref="feat/db",
            head_sha="1234567890abcdef",
        )
        session.add(pr)
        await session.flush()

        # Create Review Session
        rev_session = ReviewSession(
            pull_request_id=pr.id,
            status="completed",
            execution_time_seconds=1.5,
            model_used="llama-3.3-70b-versatile",
            prompt_tokens=300,
            completion_tokens=100,
            total_tokens=400,
            overview="Clean review",
            dry_run=True,
        )
        session.add(rev_session)
        await session.flush()

        # Create Finding
        finding = AgentFinding(
            review_session_id=rev_session.id,
            agent_name="security_agent",
            title="Weak Randomness",
            description="Use secrets instead of random",
            severity="MEDIUM",
            confidence=0.85,
            file_path="src/crypto.py",
            line_number=12,
            reasoning="random module is pseudo-random",
        )
        session.add(finding)
        await session.commit()

        # Query and verify relationships
        stmt = select(Repository).where(Repository.id == repo.id)
        result = await session.execute(stmt)
        retrieved_repo = result.scalar_one()

        assert retrieved_repo.full_name == f"test-org-{uid}/test-repo"
        assert retrieved_repo.organization_id == org.id

        finding_stmt = select(AgentFinding).where(AgentFinding.review_session_id == rev_session.id)
        f_res = await session.execute(finding_stmt)
        retrieved_findings = f_res.scalars().all()

        assert len(retrieved_findings) == 1
        assert retrieved_findings[0].title == "Weak Randomness"
        assert retrieved_findings[0].severity == "MEDIUM"
