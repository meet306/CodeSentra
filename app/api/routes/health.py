"""
Health check endpoints for service monitoring and readiness.
"""

from typing import Any

from fastapi import APIRouter, Depends

from app.api.dependencies import get_app_settings
from app.config import Settings

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=dict[str, Any])
async def health_check(settings: Settings = Depends(get_app_settings)) -> dict[str, Any]:
    """Basic health check and configuration readiness probe."""
    return {
        "status": "healthy",
        "app_name": settings.APP_NAME,
        "environment": settings.ENVIRONMENT,
        "version": "0.1.0",
        "dry_run": settings.DRY_RUN,
        "integrations": {
            "groq_configured": bool(settings.GROQ_API_KEY),
            "groq_model": settings.GROQ_MODEL,
            "github_token_configured": bool(settings.GITHUB_TOKEN),
        },
    }
