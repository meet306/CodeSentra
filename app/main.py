"""
Main FastAPI Application Entrypoint for CodeSentra.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.routes import feedback, health, review, webhook
from app.config import get_settings
from app.core.errors import CodeSentraException
from app.core.logging import logger
from app.core.metrics import get_prometheus_metrics_response
from app.database.session import init_db


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifespan context manager for startup and shutdown procedures."""
    settings = get_settings()
    logger.info(f"Starting {settings.APP_NAME} in '{settings.ENVIRONMENT}' environment")
    if settings.DRY_RUN:
        logger.info("DRY_RUN mode is ENABLED. Review findings will NOT be posted to GitHub.")
    if not settings.GROQ_API_KEY:
        logger.warning("GROQ_API_KEY is not configured! Set it in your .env file to enable AI reviews.")
    if not settings.GITHUB_TOKEN:
        logger.info("GITHUB_TOKEN is not configured. Public repositories can still be reviewed with rate limits.")

    try:
        await init_db()
    except Exception as e:
        logger.error(f"Failed to auto-initialize database tables: {e}")

    yield

    logger.info(f"Shutting down {settings.APP_NAME}")


def create_application() -> FastAPI:
    """Factory creating and configuring the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title=settings.APP_NAME,
        version="0.1.0",
        description="Advanced AI-Powered GitHub Pull Request Code Reviewer using Free Tier Technologies.",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # Global Exception Handler for CodeSentraException
    @app.exception_handler(CodeSentraException)
    async def codesentra_exception_handler(request: Request, exc: CodeSentraException) -> JSONResponse:
        logger.error(f"Application error on {request.method} {request.url.path}: {exc.message}")
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": exc.__class__.__name__,
                "message": exc.message,
                "details": exc.details,
            },
        )

    # Metrics endpoint for Prometheus
    @app.get("/metrics", include_in_schema=False)
    async def metrics():
        return get_prometheus_metrics_response()

    # Mount Routes
    # Root health probe
    app.include_router(health.router)
    # API v1 prefix routes
    app.include_router(health.router, prefix=settings.API_V1_PREFIX)
    app.include_router(review.router, prefix=settings.API_V1_PREFIX)
    app.include_router(webhook.router, prefix=settings.API_V1_PREFIX)
    app.include_router(feedback.router, prefix=settings.API_V1_PREFIX)

    return app


app = create_application()
