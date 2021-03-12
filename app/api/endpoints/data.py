import logging
import uuid
from typing import Any
from fastapi import APIRouter
from fastapi.responses import JSONResponse, HTMLResponse
from starlette.requests import Request
import yaml

import xarray as xr

from ...store import JOB_RESULTS, CENTRAL_STORE
from ..utils import get_ds
from ...models import DataRequest
from .utils.helpers import perform_fetch
from .download import router as download_router
from .ship_data import router as ship_data_router

logger = logging.getLogger(__name__)
logging.root.setLevel(level=logging.INFO)

router = APIRouter()
router.include_router(download_router, prefix="/download")
router.include_router(ship_data_router, prefix="/ship")


# ------------------ API ROUTES --------------------------------
@router.get("/")
def list_datasets():
    return get_ds()

# ------------ CATALOG ENDPOINTS ------------------------
@router.get("/catalog")
async def get_catalog(streams_only: bool = False) -> JSONResponse:
    try:
        if "intake_catalog" in CENTRAL_STORE:
            catalog = CENTRAL_STORE["intake_catalog"]
            if not streams_only:
                result = yaml.load(catalog.yaml(), Loader=yaml.SafeLoader)[
                    'sources'
                ]
                result[catalog.name].update({"data_streams": list(catalog)})
            else:
                result = {"data_streams": list(catalog)}
            return JSONResponse(status_code=200, content=result)
        else:
            return JSONResponse(
                status_code=200,
                content={
                    "message": "Catalog not available. Please try again in a few minutes."
                },
            )
    except Exception as e:
        return JSONResponse(
            status_code=400, content={"message": f"{e}", "type": f"{type(e)}"}
        )


@router.get("/catalog/{data_stream}")
async def view_data_stream_catalog(data_stream: str) -> Any:
    try:
        if "intake_catalog" in CENTRAL_STORE:
            catalog = CENTRAL_STORE["intake_catalog"]
            source = catalog[data_stream]
            return JSONResponse(status_code=200, content=source.describe())
        else:
            return JSONResponse(
                status_code=200,
                content={
                    "message": "Catalog not available. Please try again in a few minutes."
                },
            )
    except Exception as e:
        return JSONResponse(
            status_code=400, content={"message": f"{e}", "type": f"{type(e)}"}
        )


@router.get("/catalog/{data_stream}/view")
async def view_data_stream_dataset(data_stream: str) -> Any:
    try:
        if "intake_catalog" in CENTRAL_STORE:
            catalog = CENTRAL_STORE["intake_catalog"]
            dataset = catalog[data_stream].to_dask()

            with xr.set_options(display_style='html'):
                return HTMLResponse(dataset._repr_html_())
        else:
            return JSONResponse(
                status_code=200,
                content={
                    "message": "Catalog not available. Please try again in a few minutes."
                },
            )
    except Exception as e:
        return JSONResponse(
            status_code=400, content={"message": f"{e}", "type": f"{type(e)}"}
        )
# ------------ END CATALOG ENDPOINTS ------------------------


@router.get("/job/{uid}")
def get_job(uid: str):
    job_uuid = uuid.UUID(uid)
    if job_uuid in JOB_RESULTS:
        return JOB_RESULTS[job_uuid]
    return {
        "status": "error",
        "result": None,
        "msg": f"Job {job_uuid} not found.",
    }


@router.post("/", status_code=202)
def request_data(request: Request, data_request: DataRequest):
    try:
        request_uuid = perform_fetch(data_request)

        return {
            "status": "success",
            "job_uuid": str(request_uuid),
            "result_url": f"/data/job/{str(request_uuid)}",
            "msg": f"Job {str(request_uuid)} created.",
        }
    except Exception as e:
        return JSONResponse(
            content={
                "status": "failed",
                "job_uuid": None,
                "result_url": None,
                "msg": f"Error occured: {e}",
            },
            status_code=500,
        )
