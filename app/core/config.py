import os
import fsspec

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
