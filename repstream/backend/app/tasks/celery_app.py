"""Celery application configuration for RepStream async tasks."""
from celery import Celery
from celery.schedules import crontab

from app.config import settings

celery_app = Celery(
    "repstream",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "app.tasks.refresh_territory",
        "app.tasks.refresh_new_writers",
        "app.tasks.refresh_objections",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)

# Weekly batch schedule: every Monday at 02:00 UTC
celery_app.conf.beat_schedule = {
    "refresh-territory-prioritization-weekly": {
        "task": "app.tasks.refresh_territory.refresh_all_territories",
        "schedule": crontab(hour=2, minute=0, day_of_week="monday"),
    },
    "refresh-new-writers-weekly": {
        "task": "app.tasks.refresh_new_writers.refresh_all_new_writers",
        "schedule": crontab(hour=2, minute=30, day_of_week="monday"),
    },
    "refresh-objections-weekly": {
        "task": "app.tasks.refresh_objections.refresh_all_objections",
        "schedule": crontab(hour=3, minute=0, day_of_week="monday"),
    },
}
