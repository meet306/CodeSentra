"""
GitHub Webhook Endpoint.
Receives, verifies HMAC signature, and dispatches webhook events.
"""

from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request, status

from app.config import get_settings
from app.core.errors import CodeSentraException
from app.core.logging import logger
from app.services.gateway.verifier import verify_github_signature
from app.services.webhook.processor import WebhookProcessor

router = APIRouter(prefix="/webhook", tags=["Webhook"])

# Global singleton processor
_processor = WebhookProcessor()


@router.post(
    "/github",
    status_code=status.HTTP_200_OK,
    summary="Receive GitHub Webhook Events",
    description="Authenticates incoming webhook via HMAC SHA-256 and dispatches PR review workflow.",
)
async def github_webhook_endpoint(
    request: Request,
    x_github_event: str = Header(..., alias="X-GitHub-Event"),
    x_hub_signature_256: str | None = Header(None, alias="X-Hub-Signature-256"),
    x_github_delivery: str | None = Header(None, alias="X-GitHub-Delivery"),
) -> dict[str, Any]:
    """Endpoint processing GitHub webhooks with HMAC SHA-256 verification."""
    settings = get_settings()

    # 1. Read raw request body bytes for signature verification
    payload_body = await request.body()

    # 2. Verify HMAC SHA-256 signature
    try:
        verify_github_signature(
            payload_body=payload_body,
            signature_header=x_hub_signature_256,
            secret=settings.GITHUB_WEBHOOK_SECRET,
        )
    except CodeSentraException as e:
        logger.error(f"Webhook authentication rejected: {e.message}")
        raise HTTPException(status_code=e.status_code, detail=e.message)

    # 3. Handle GitHub 'ping' event
    if x_github_event == "ping":
        logger.info(f"Received GitHub ping event (Delivery ID: {x_github_delivery})")
        return {"status": "pong", "message": "CodeSentra webhook receiver active and verified."}

    # 4. Parse JSON payload
    try:
        payload = await request.json()
    except Exception as e:
        logger.error(f"Malformed JSON payload in webhook: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Malformed JSON payload.")

    # 5. Handle pull_request events
    if x_github_event == "pull_request":
        result = await _processor.process_pull_request_event(
            payload=payload,
            delivery_id=x_github_delivery,
        )
        return result

    logger.info(f"Ignoring non-PR event: '{x_github_event}'")
    return {"status": "ignored", "event": x_github_event}
