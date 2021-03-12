import logging
import os

from dask.distributed import Client

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from starlette.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates
import intake

from .api.main import api_router
from .api.endpoints import data
from .core.config import Settings
from .store import CENTRAL_STORE
from .scripts import LoadDataCatalog, LoadShipData

logging.root.setLevel(level=logging.INFO)
logger = logging.getLogger('uvicorn')

settings = Settings()
app = FastAPI(title=settings.API_TITLE, description=settings.API_DESCRIPTION)

app.state.static = StaticFiles(directory=os.path.join(settings.BASE_PATH, "static"))
app.state.templates = Jinja2Templates(
    directory=os.path.join(settings.BASE_PATH, "templates")
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)
app.include_router(data.router, prefix="/data", tags=["data"])
app.mount("/static", app.state.static, name="static")


@app.on_event("startup")
async def startup_event():
    LoadDataCatalog()
    LoadShipData()
