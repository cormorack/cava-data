import datetime
from .config import settings

broker_url = settings.RABBITMQ_URI

task_routes = {
    "app.api.workers.tasks.perform_fetch_task": {"queue": "data-queue"}
}

# Results configs
result_backend = settings.REDIS_URI
result_expires = datetime.timedelta(hours=1)
