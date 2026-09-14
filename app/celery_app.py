from celery import Celery

from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "invoice_processing",
    broker=settings.celery_broker_url,
    include=["app.tasks"],
)
celery_app.conf.update(
    enable_utc=True,
    timezone="UTC",
    task_serializer="json",
    accept_content=["json"],
    task_ignore_result=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    broker_connection_retry_on_startup=True,
)
