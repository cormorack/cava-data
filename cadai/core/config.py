import os
import fsspec

API_TITLE = "Cabled Array Data Access Interface"
API_DESCRIPTION = "Cabled Array Data Streams"

CORS_ORIGINS = ["http://localhost", "http://localhost:8000"]

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
