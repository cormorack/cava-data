from celery import Celery
from .config import settings

celery_app = Celery(
    "cava-data", broker=settings.RABBITMQ_URI, backend=settings.REDIS_URI
)

celery_app.conf.task_routes = {
    "app.api.workers.tasks.perform_fetch_task": {"queue": "data-queue"}
}
