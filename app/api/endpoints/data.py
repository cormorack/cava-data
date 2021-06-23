import logging
from typing import Any
from fastapi import APIRouter
from fastapi.responses import JSONResponse, HTMLResponse
from starlette.requests import Request
import yaml

import xarray as xr
from dask.utils import memory_repr
import numpy as np

from app.core.celery_app import celery_app
from ...store import CENTRAL_STORE
from ..utils import get_ds
from ...models import DataRequest, CancelConfig
from .download import router as download_router
from .ship_data import router as ship_data_router
from ..workers.tasks import perform_fetch_task
from ..workers.data_fetcher import get_delayed_ds

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
                    "message": "Catalog not available. Please try again in a few minutes."  # noqa
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
                    "message": "Catalog not available. Please try again in a few minutes."  # noqa
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
                    "message": "Catalog not available. Please try again in a few minutes."  # noqa
                },
            )
    except Exception as e:
        return JSONResponse(
            status_code=400, content={"message": f"{e}", "type": f"{type(e)}"}
        )


# ------------ END CATALOG ENDPOINTS ------------------------


@router.get("/job/{uid}")
def get_job(uid: str):
    task = perform_fetch_task.AsyncResult(uid)
    response = {}
    if task.state == 'PENDING':
        # job did not start yet
        response.update(
            {
                'state': task.state,
                'status': 'pending',
                'result': None,
                'msg': f'Job {uid} has not started.',
            }
        )
    elif task.state != 'FAILURE':
        # pending/success
        response.update({'state': task.state})
        response.update(task.info)
    else:
        # something went wrong in the background job
        response.update(
            {
                'state': task.state,
                'status': 'job-exception',
                'result': None,
                'msg': str(task.info),  # this is the exception raised
            }
        )
    return response


@router.post("/job/{uid}/cancel", status_code=202)
def cancel_job(uid: str, cancel_config: CancelConfig):
    signal = cancel_config.signal
    try:
        if signal not in ['SIGTERM', 'SIGKILL']:
            raise ValueError(f"{signal} is not a valid value.")
        celery_app.control.revoke(uid, terminate=True, signal=signal)
        return {
            "status": "success",
            "signal": signal,
            "msg": f"Job {uid} successfully cancelled.",
        }
    except Exception as e:
        return JSONResponse(
            content={
                "status": "failed",
                "signal": signal,
                "msg": f"Error occured: {e}",
            },
            status_code=500,
        )


@router.post("/check", status_code=202)
def data_request_check(request: Request, data_request: DataRequest):
    try:
        req = data_request.dict()
        # Figure out the maximum data size request possible
        # Some functionality same as perform_fetch_task in tasks.py
        request_params = req["ref"].split(",")
        # TODO: For now use z as color, need to change in future, esp for 3D
        axis_params = {
            "x": req['x'],
            "y": req['y'],
            "z": req['color'],
        }
        ds_list = get_delayed_ds(
            request_params, axis_params, include_dataset=False
        )
        cleaned_list = {
            k: {i: int(j) for i, j in v.items() if i == 'total_size'}
            for k, v in ds_list.items()
        }
        max_data_size = np.sum([v['total_size'] for v in ds_list.values()])
        return {
            "status": "success",
            "data_sizes": cleaned_list,
            "msg": f"Max data request: {memory_repr(max_data_size)}",
        }
    except Exception as e:
        return JSONResponse(
            content={
                "status": "failed",
                "data_sizes": None,
                "msg": f"Error occured: {e}",
            },
            status_code=500,
        )


@router.post("/", status_code=202)
def request_data(request: Request, data_request: DataRequest):
    try:
        task = perform_fetch_task.apply_async(args=(data_request.dict(),))
        request_uuid = task.id
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
