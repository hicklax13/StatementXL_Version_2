"""
Celery application configuration.

Configures Celery for background task processing with Redis as the broker.
"""
import os

from celery import Celery

# Redis URL for Celery broker and result backend
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Create Celery application
celery_app = Celery(
    "statementxl",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["backend.tasks.pdf_tasks"],
)

# Celery configuration
celery_app.conf.update(
    # Task settings
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,

    # Task execution settings
    task_acks_late=True,  # Acknowledge after task completes (not before)
    task_reject_on_worker_lost=True,  # Requeue if worker dies
    task_time_limit=600,  # 10 minute hard limit
    task_soft_time_limit=540,  # 9 minute soft limit (allows cleanup)

    # Result settings
    result_expires=86400,  # Results expire after 24 hours

    # Worker settings
    worker_prefetch_multiplier=1,  # Process one task at a time
    worker_concurrency=4,  # Number of worker processes

    # Retry settings
    task_default_retry_delay=60,  # 1 minute between retries
    task_max_retries=3,

    # Beat scheduler (for periodic tasks)
    beat_schedule={
        "cleanup-expired-jobs": {
            "task": "backend.tasks.pdf_tasks.cleanup_expired_jobs",
            "schedule": 3600.0,  # Every hour
        },
    },
)

# Optional: Configure task routes for different queues
celery_app.conf.task_routes = {
    "backend.tasks.pdf_tasks.process_pdf": {"queue": "pdf_processing"},
    "backend.tasks.pdf_tasks.export_excel": {"queue": "excel_export"},
}
