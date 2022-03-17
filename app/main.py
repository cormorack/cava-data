import logging
import os


from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from starlette.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates

from prometheus_fastapi_instrumentator import Instrumentator

from .api.main import api_router
from .api.endpoints import data
from .core.config import settings
from .scripts import LoadDataCatalog, LoadShipData
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

app.state.static = StaticFiles(directory=os.path.join(settings.BASE_PATH, "static"))
app.state.templates = Jinja2Templates(
    directory=os.path.join(settings.BASE_PATH, "templates")
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

# app.include_router(api_router)
app.include_router(data.router, prefix="/data", tags=["data"])
app.mount("/data/static", app.state.static, name="static")


@app.on_event("startup")
async def startup_event():
    LoadDataCatalog()
    await RedisDependency().init()
    # LoadShipData()

# Prometheus instrumentation
Instrumentator().instrument(app).expose(
    app, endpoint="/data/metrics", include_in_schema=False
)
