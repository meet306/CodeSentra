"""
Celery Application Configuration.
Uses Redis broker and result backend with exponential retry settings.
"""

from celery import Celery

from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "codesentra_worker",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,  # 5 min hard limit per task
    task_soft_time_limit=240,
    worker_prefetch_multiplier=1,  # Prevent worker overload
    task_acks_late=True,  # Re-queue task if worker crashes
)
