"""
Developer Feedback API endpoints.
Collects developer feedback on reviews and individual findings to guide convention learning.
"""

from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.core.logging import logger
from app.services.learner.learner_service import LearnerService

router = APIRouter(prefix="/feedback", tags=["Feedback"])


class FeedbackRequest(BaseModel):
    """Payload to record developer feedback on code review findings."""

    repo_full_name: str = Field(..., description="Repository full name (e.g. 'octocat/Hello-World')")
    feedback_type: str = Field(
        ...,
        description="Type of feedback: ACCEPTED, REJECTED, FALSE_POSITIVE, THUMBS_UP, THUMBS_DOWN",
    )
    finding_id: str | None = Field(default=None, description="UUID of the specific finding if applicable")
    review_comment_id: str | None = Field(default=None, description="GitHub review comment ID if applicable")
    comment: str | None = Field(default=None, description="Optional developer explanation or feedback note")


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Submit developer feedback on review findings",
    description="Records developer acceptance, rejection, or false-positive reports to train the learner system.",
)
async def submit_developer_feedback(request: FeedbackRequest) -> dict[str, Any]:
    """Endpoint recording developer feedback."""
    logger.info(f"Received developer feedback: {request.feedback_type} for {request.repo_full_name}")
    try:
        learner = LearnerService()
        result = await learner.record_feedback(
            repo_full_name=request.repo_full_name,
            feedback_type=request.feedback_type,
            finding_id=request.finding_id,
            review_comment_id=request.review_comment_id,
            comment=request.comment,
        )
        return result
    except Exception as e:
        logger.error(f"Failed to record developer feedback: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save feedback: {str(e)}",
        )
