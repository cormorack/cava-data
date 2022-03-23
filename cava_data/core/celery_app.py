from celery import Celery
from .config import settings
from cava_data.core import celeryconfig

celery_app = Celery("cava-data")

celery_app.config_from_object(celeryconfig)
