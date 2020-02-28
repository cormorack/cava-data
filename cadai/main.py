import logging
import os

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates

from cadai.api.main import api_router
from cadai.core.config import CORS_ORIGINS, API_TITLE, API_DESCRIPTION, BASE_PATH
from cadai.scripts import load_datasets

logger = logging.getLogger(__name__)
logging.root.setLevel(level=logging.INFO)

app = FastAPI(title=API_TITLE, description=API_DESCRIPTION)

app.state.static = StaticFiles(directory=os.path.join(BASE_PATH, "static"))
app.state.templates = Jinja2Templates(directory=os.path.join(BASE_PATH, "templates"))

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)
app.mount("/static", app.state.static, name="static")


@app.on_event("startup")
async def startup_event():
    load_datasets(app)
