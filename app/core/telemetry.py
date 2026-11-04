"""
Telemetry and LLM observability integration (Langfuse self-hosted).
Safely acts as a no-op when Langfuse keys are absent, preserving memory and CPU.
"""

from typing import Any

from app.config import get_settings
from app.core.logging import logger

_langfuse_client = None


def get_telemetry_client() -> Any | None:
    """Returns self-hosted Langfuse client if configured; otherwise returns None."""
    global _langfuse_client
    settings = get_settings()

    if not settings.LANGFUSE_PUBLIC_KEY or not settings.LANGFUSE_SECRET_KEY:
        return None

    if _langfuse_client is None:
        try:
            from langfuse import Langfuse
            _langfuse_client = Langfuse(
                public_key=settings.LANGFUSE_PUBLIC_KEY,
                secret_key=settings.LANGFUSE_SECRET_KEY,
                host=settings.LANGFUSE_HOST,
            )
            logger.info("Initialized Langfuse telemetry client.")
        except ImportError:
            logger.debug("Langfuse library not installed; telemetry tracing disabled.")
            return None
        except Exception as e:
            logger.warning(f"Could not connect to self-hosted Langfuse: {e}")
            return None

    return _langfuse_client


def trace_agent_execution(
    agent_name: str,
    pr_id: str,
    duration: float,
    findings_count: int,
    tokens: dict[str, int] | None = None,
) -> None:
    """Logs telemetry trace to Langfuse if enabled."""
    client = get_telemetry_client()
    if client is None:
        return

    try:
        trace = client.trace(
            name=f"agent-{agent_name}",
            user_id="codesentra-system",
            metadata={"pr_id": pr_id, "findings_count": findings_count},
        )
        trace.generation(
            name=agent_name,
            model=get_settings().GROQ_MODEL,
            usage=tokens or {},
        )
    except Exception as e:
        logger.warning(f"Telemetry recording error: {e}")
