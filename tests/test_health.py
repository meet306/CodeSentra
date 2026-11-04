"""
Unit tests for the health check endpoints.
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_root_health_check(async_client: AsyncClient) -> None:
    """Verifies that the root /health endpoint returns healthy status and metadata."""
    response = await async_client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data
    assert "integrations" in data
    assert "groq_configured" in data["integrations"]


@pytest.mark.asyncio
async def test_api_v1_health_check(async_client: AsyncClient) -> None:
    """Verifies that /api/v1/health returns matching healthy status."""
    response = await async_client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["app_name"] == "CodeSentra AI PR Reviewer"
