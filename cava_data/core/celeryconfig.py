import datetime
from .config import settings

broker_url = str(settings.RABBITMQ_URI)
if settings.RABBITMQ_URI.startswith('sqs://'):
    broker_transport_options = {'region': 'us-west-2'}

task_routes = {
    "cava_data.api.workers.tasks.perform_fetch_task": {
        "queue": settings.DATA_QUEUE
    }
}
task_create_missing_queues = True

# Results configs
result_backend = str(settings.REDIS_URI)
result_expires = datetime.timedelta(hours=1)
