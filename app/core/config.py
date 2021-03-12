import os
import fsspec

from typing import Dict, List
from pydantic import BaseSettings


class Settings(BaseSettings):
    API_TITLE: str = "Cabled Array Data Access Interface"
    API_DESCRIPTION: str = "Cabled Array Data Streams"

    CORS_ORIGINS: List[str] = [
        "http://localhost",
        "http://localhost:8000",
        "https://api-dev.ooica.net",
        "https://api.interactiveoceans.washington.edu",
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
    RABBITMQ_URI: str = "amqp://guest@rabbitmq-service:5672//"

    # Cache service
    REDIS_URI: str = "redis://redis-service"


API_TITLE = "Cabled Array Data Access Interface"
API_DESCRIPTION = "Cabled Array Data Streams"

CORS_ORIGINS = [
    "http://localhost",
    "http://localhost:8000",
    "https://api-dev.ooica.net",
    "https://api.interactiveoceans.washington.edu",
]

BASE_PATH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FILE_SYSTEMS = {
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

DATA_BUCKET = 'ooi-data'
CADAI_BUCKET = 'ooi-data-cadai'
SHIP_DATA_FOLDER = 'ship_data'
SHIP_DATA_SOURCE = f'{SHIP_DATA_FOLDER}/source.json'
SHIP_DATA_LABEL_MAP = f'{SHIP_DATA_FOLDER}/label_map.json'
SHIP_DATA_PROFILES = f'{SHIP_DATA_FOLDER}/profiles'
SHIP_DATA_DISCRETE = f'{SHIP_DATA_FOLDER}/discrete'

settings = Settings()
