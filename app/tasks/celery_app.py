"""
Celery application instance. Run a worker with:

    celery -A app.tasks.celery_app worker --loglevel=info

The broker and result backend both use Redis (separate logical DBs from the
one used for caching/rate-limiting/blacklisting, see app.core.config).
"""

from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "blog_api",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.tasks.email_tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=60,
    task_soft_time_limit=45,
    worker_max_tasks_per_child=1000,
    broker_connection_retry_on_startup=True,
)
