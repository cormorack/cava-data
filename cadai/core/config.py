import os

API_TITLE = "Cabled Array Data Access Interface"
API_DESCRIPTION = "Cabled Array Data Streams"

CORS_ORIGINS = [
    "http://localhost",
    "http://localhost:8000",
]

BASE_PATH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
