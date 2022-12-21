import logging


from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from starlette.middleware.cors import CORSMiddleware

from prometheus_fastapi_instrumentator import Instrumentator

from .api.endpoints import data
from .core.config import settings
from .scripts import LoadDataCatalog
from .cache.redis import RedisDependency

logging.root.setLevel(level=logging.INFO)
logger = logging.getLogger('uvicorn')

app = FastAPI(
    title=settings.SERVICE_NAME,
    openapi_url=settings.OPENAPI_URL,
    docs_url=settings.DOCS_URL,
    redoc_url=None,
    version=settings.CURRENT_API_VERSION,
    description=settings.SERVICE_DESCRIPTION,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    # Regex for dev in netlify
    allow_origin_regex='https://.*cava-portal\.netlify\.app',
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(data.router, prefix="/data", tags=["data"])


# @app.on_event("startup")
# async def startup_event():
    # LoadDataCatalog()
    # await RedisDependency().init()
    # LoadShipData()

# Prometheus instrumentation
Instrumentator().instrument(app).expose(
    app, endpoint="/data/metrics", include_in_schema=False
)
