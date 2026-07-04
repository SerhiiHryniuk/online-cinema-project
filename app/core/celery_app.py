from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

celery_app = Celery(
    "cinema",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.tasks.cleanup", "app.tasks.emails"],
)

celery_app.conf.timezone = "UTC"

celery_app.conf.beat_schedule = {
    "delete-expired-activation-tokens": {
        "task": "app.tasks.cleanup.delete_expired_activation_tokens",
        "schedule": crontab(minute="0", hour="*"),
    },
}
