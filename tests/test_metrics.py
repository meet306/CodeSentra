"""
Unit tests for Prometheus metrics and Telemetry integration.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.metrics import (
    FINDINGS_GENERATED_TOTAL,
    GROQ_TOKENS_TOTAL,
    REVIEWS_TOTAL,
    WEBHOOK_EVENTS_TOTAL,
)
from app.core.telemetry import trace_agent_execution
from app.main import create_application


@pytest.mark.asyncio
async def test_metrics_endpoint() -> None:
    """Verifies that GET /metrics returns raw Prometheus exposition format."""
    # Increment counters
    WEBHOOK_EVENTS_TOTAL.labels(event_type="pull_request", action="opened").inc()
    REVIEWS_TOTAL.labels(status="success").inc()
    GROQ_TOKENS_TOTAL.labels(token_type="total").inc(120)
    FINDINGS_GENERATED_TOTAL.labels(severity="HIGH", agent_name="security_agent").inc()

    app = create_application()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/metrics")

    assert response.status_code == 200
    assert "text/plain" in response.headers.get("content-type", "")
    content = response.text
    assert "codesentra_webhook_events_total" in content
    assert "codesentra_reviews_total" in content
    assert "codesentra_groq_tokens_total" in content


def test_telemetry_no_op_without_keys() -> None:
    """Verifies trace_agent_execution safely executes without error when Langfuse keys are absent."""
    # Should not raise exception
    trace_agent_execution(
        agent_name="static_agent",
        pr_id="test/repo#1",
        duration=1.2,
        findings_count=2,
        tokens={"total_tokens": 100},
    )
