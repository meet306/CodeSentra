"""
FastAPI dependency injection providers.
"""

from fastapi import Depends

from app.config import Settings, get_settings
from app.integrations.github import GitHubClient
from app.integrations.groq import GroqClient
from app.services.orchestrator.orchestrator_service import OrchestratorService
from app.services.reviewer.review_service import ReviewService


def get_app_settings() -> Settings:
    """Dependency for application settings."""
    return get_settings()


def get_github_client(settings: Settings = Depends(get_app_settings)) -> GitHubClient:
    """Dependency for GitHub API client."""
    return GitHubClient(settings=settings)


def get_groq_client(settings: Settings = Depends(get_app_settings)) -> GroqClient:
    """Dependency for Groq client."""
    return GroqClient(settings=settings)


def get_review_service(
    github_client: GitHubClient = Depends(get_github_client),
    groq_client: GroqClient = Depends(get_groq_client),
    settings: Settings = Depends(get_app_settings),
) -> ReviewService:
    """Dependency for ReviewService instance."""
    return ReviewService(
        github_client=github_client,
        groq_client=groq_client,
        settings=settings,
    )


def get_orchestrator_service(
    github_client: GitHubClient = Depends(get_github_client),
    groq_client: GroqClient = Depends(get_groq_client),
    settings: Settings = Depends(get_app_settings),
) -> OrchestratorService:
    """Dependency for multi-agent OrchestratorService instance."""
    return OrchestratorService(
        github_client=github_client,
        groq_client=groq_client,
        settings=settings,
    )
