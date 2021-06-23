import os
import fsspec

from typing import Dict, List
from pydantic import BaseSettings


class Settings(BaseSettings):
    SERVICE_NAME = "Cabled Array Data Access Service"
    SERVICE_ID = "data"
    OPENAPI_URL = f"/{SERVICE_ID}/openapi.json"
    DOCS_URL = f"/{SERVICE_ID}/"
    SERVICE_DESCRIPTION = """Data service for Interactive Oceans."""

    # API VERSION
    CURRENT_API_VERSION = 2.0

    CORS_ORIGINS: List[str] = [
        "http://localhost",
        "http://localhost:8000",
        "http://localhost:5000",
        "http://localhost:4000",
        "https://appdev.ooica.net",
        "https://app-dev.ooica.net",
        "https://app.interactiveoceans.washington.edu",
        "https://api-dev.ooica.net",
        "https://api.interactiveoceans.washington.edu",
        "https://api-development.ooica.net",
        "https://cava-portal.netlify.app",
    ]

    BASE_PATH: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    FILE_SYSTEMS: Dict = {
        "minio_s3": fsspec.filesystem(
            "s3", client_kwargs={"endpoint_url": "http://minio:9000"}
        ),
        "aws_s3": fsspec.filesystem(
            "s3",
            skip_instance_cache=True,
            use_listings_cache=False,
            config_kwargs={'max_pool_connections': 1000},
        ),
    }

    DATA_BUCKET: str = 'ooi-data'
    CADAI_BUCKET: str = 'ooi-data-cadai'
    SHIP_DATA_FOLDER: str = 'ship_data'
    SHIP_DATA_SOURCE: str = f'{SHIP_DATA_FOLDER}/source.json'
    SHIP_DATA_LABEL_MAP: str = f'{SHIP_DATA_FOLDER}/label_map.json'
    SHIP_DATA_PROFILES: str = f'{SHIP_DATA_FOLDER}/profiles'
    SHIP_DATA_DISCRETE: str = f'{SHIP_DATA_FOLDER}/discrete'
    DATA_CATALOG_FILE: str = "https://ooi-data.github.io/catalog.yaml"

    # Message queue
    RABBITMQ_URI: str = os.environ.get("RABBITMQ_URI", "amqp://guest@rabbitmq-service:5672//")

    # Cache service
    REDIS_URI: str = os.environ.get("REDIS_URI", "redis://redis-service")

settings = Settings()
