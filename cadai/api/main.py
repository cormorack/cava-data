import logging

from fastapi import APIRouter
from starlette.requests import Request

import xarray as xr
import fsspec

from cadai.store import DATASETS_STORE
from cadai.api.utils import get_ds

logger = logging.getLogger(__name__)
logging.root.setLevel(level=logging.INFO)

api_router = APIRouter()


@api_router.get("/")
async def home(request: Request):
    datasets = get_ds()
    return request.app.state.templates.TemplateResponse(
        "index.html", {"request": request, "datasets": datasets}
    )


@api_router.get("/datasets")
async def get_datasets():
    datasets = get_ds()
    return datasets


@api_router.post("/refresh/{dataset_id}")
async def refresh_dataset(request: Request, dataset_id: str):
    if dataset_id:
        if dataset_id in DATASETS_STORE:
            logger.info(f"Refreshing dataset: {dataset_id}.")
            ds = xr.open_zarr(
                fsspec.get_mapper(DATASETS_STORE[dataset_id].zarr_url),
                consolidated=True)
            DATASETS_STORE[dataset_id].set_ds(ds)
            for r in request.app.routes:
                if r.path == f"/{dataset_id}":
                    request.app.routes.remove(r)
            request.app.mount(f"/{dataset_id}", DATASETS_STORE[dataset_id].app)
    return {"status": "success", "dataset_id": dataset_id}
