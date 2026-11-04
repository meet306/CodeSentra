"""
Prometheus Metrics instrumentation for CodeSentra.
Exposes runtime counters, histograms, and gauge metrics for observability.
"""

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Histogram,
    generate_latest,
)
from starlette.responses import Response

# 1. Webhook metrics
WEBHOOK_EVENTS_TOTAL = Counter(
    "codesentra_webhook_events_total",
    "Total incoming GitHub webhook events",
    ["event_type", "action"],
)

# 2. Review execution metrics
REVIEWS_TOTAL = Counter(
    "codesentra_reviews_total",
    "Total Pull Request reviews processed",
    ["status"],  # success, failed, skipped
)

# 3. Agent latency histograms
AGENT_DURATION_SECONDS = Histogram(
    "codesentra_agent_duration_seconds",
    "Execution duration for specialized AI review agents in seconds",
    ["agent_name"],
    buckets=(0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0),
)

# 4. Groq Free Tier token tracking
GROQ_TOKENS_TOTAL = Counter(
    "codesentra_groq_tokens_total",
    "Total Groq tokens consumed across all agent calls",
    ["token_type"],  # prompt, completion, total
)

# 5. Finding distribution counter
FINDINGS_GENERATED_TOTAL = Counter(
    "codesentra_findings_total",
    "Total code review findings emitted by severity and agent",
    ["severity", "agent_name"],
)


def get_prometheus_metrics_response() -> Response:
    """Generates the Prometheus text metrics response."""
    data = generate_latest()
    return Response(content=data, media_type=CONTENT_TYPE_LATEST)

