"""
Pull Request review trigger endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import get_review_service
from app.core.errors import (
    CodeSentraException,
    GitHubAPIError,
    GroqAPIError,
    RateLimitExceededError,
)
from app.core.logging import logger
from app.schemas.review import ReviewRequest, ReviewResponse
from app.services.reviewer.review_service import ReviewService

router = APIRouter(prefix="/review", tags=["Review"])


@router.post(
    "/pr",
    response_model=ReviewResponse,
    status_code=status.HTTP_200_OK,
    summary="Trigger AI code review for a GitHub Pull Request",
    description="Fetches PR diff from GitHub, runs Groq LLM analysis, and returns structured findings.",
)
async def review_pull_request_endpoint(
    request: ReviewRequest,
    review_service: ReviewService = Depends(get_review_service),
) -> ReviewResponse:
    """Initiates an on-demand code review for a given repository and PR number."""
    logger.info(f"Received review request for PR: {request.repo_owner}/{request.repo_name}#{request.pr_number}")
    try:
        response = await review_service.review_pull_request(request)
        return response
    except RateLimitExceededError as e:
        logger.warning(f"Rate limit hit during review: {e.message}")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=e.message,
        )
    except GitHubAPIError as e:
        logger.error(f"GitHub API failure: {e.message}")
        raise HTTPException(
            status_code=e.status_code if e.status_code in [400, 401, 403, 404] else status.HTTP_502_BAD_GATEWAY,
            detail=e.message,
        )
    except GroqAPIError as e:
        logger.error(f"Groq API failure: {e.message}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=e.message,
        )
    except CodeSentraException as e:
        logger.error(f"Domain error during review: {e.message}")
        raise HTTPException(
            status_code=e.status_code,
            detail=e.message,
        )
    except Exception as e:
        logger.exception(f"Unexpected error executing PR review: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected internal error occurred: {str(e)}",
        )
