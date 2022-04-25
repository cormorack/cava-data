from datetime import timedelta
import logging
from typing import Any
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse, HTMLResponse, Response, RedirectResponse
from starlette.requests import Request
import yaml
import msgpack
import fsspec
import os

import xarray as xr
from dask.utils import memory_repr
import numpy as np
import redis.asyncio as aioredis
import intake

from cava_data.core.celery_app import celery_app
from cava_data.core.celeryconfig import result_expires
from cava_data.core.config import settings
from cava_data.cache.redis import redis_dependency
from ...models import DataRequest, CancelConfig
from .download import router as download_router
# from .ship_data import router as ship_data_router
from ..workers.tasks import perform_fetch_task
from ..workers.data_fetcher import get_delayed_ds

logger = logging.getLogger(__name__)
logging.root.setLevel(level=logging.INFO)

router = APIRouter()
router.include_router(download_router, prefix="/download")
# router.include_router(ship_data_router, prefix="/ship")

async def get_catalog():
    return intake.open_catalog(settings.DATA_CATALOG_FILE)


# ------------------ API ROUTES --------------------------------
@router.get("/status")
def get_service_status():
    return {"status": "running", "message": "Data service is up."}


# ------------ CATALOG ENDPOINTS ------------------------
@router.get("/catalog")
async def get_catalog(streams_only: bool = False, catalog = Depends(get_catalog)) -> JSONResponse:
    try:
        if not streams_only:
            result = yaml.load(catalog.yaml(), Loader=yaml.SafeLoader)[
                'sources'
            ]
            result[catalog.name].update({"data_streams": list(catalog)})
        else:
            result = {"data_streams": list(catalog)}
        return JSONResponse(status_code=200, content=result)
    except Exception as e:
        return JSONResponse(
            status_code=400, content={"message": f"{e}", "type": f"{type(e)}"}
        )


@router.get("/catalog/{data_stream}")
async def view_data_stream_catalog(data_stream: str, catalog = Depends(get_catalog)) -> Any:
    try:
        source = catalog[data_stream]
        return JSONResponse(status_code=200, content=source.describe())
    except Exception as e:
        return JSONResponse(
            status_code=400, content={"message": f"{e}", "type": f"{type(e)}"}
        )


@router.get("/catalog/{data_stream}/view")
async def view_data_stream_dataset(data_stream: str, catalog = Depends(get_catalog)) -> Any:
    try:
        dataset = catalog[data_stream].to_dask()

        with xr.set_options(display_style='html'):
            return HTMLResponse(dataset._repr_html_())
    except Exception as e:
        return JSONResponse(
            status_code=400, content={"message": f"{e}", "type": f"{type(e)}"}
        )


# ------------ END CATALOG ENDPOINTS ------------------------


@router.get("/job/{uid}")
async def get_job(uid: str, version: str = str(settings.CURRENT_API_VERSION)):
    try:
        results_bucket = "io2-portal-results"
        cache_location = f"s3://{results_bucket}"
        object_url = f"https://{results_bucket}.s3.{settings.REGION}.amazonaws.com/{uid}"
        fs = fsspec.get_mapper(cache_location).fs
        target_url = os.path.join(
            cache_location, uid
        )

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

        if version == str(settings.CURRENT_API_VERSION):
            return JSONResponse(status_code=200, content=response)
        elif version == "2.1":
            if response.get('status') == "success" and fs.exists(target_url):
                    return RedirectResponse(object_url)
            with fs.open(target_url, mode='wb') as f:
                f.write(msgpack.packb(response))
            return RedirectResponse(object_url)
        else:
            return JSONResponse(
                status_code=400, content=f"Version {version} is invalid"
            )
    except Exception as e:
        return JSONResponse(
            content={
                'status': 'query-exception',
                'state': None,
                'result': None,
                'msg': f"Error occured during query: {str(e)}",
            },
            status_code=500,
        )


@router.post("/job/{uid}/cancel", status_code=202)
def cancel_job(uid: str, cancel_config: CancelConfig):
    signal = cancel_config.signal
    try:
        if signal not in ['SIGTERM', 'SIGKILL', 'SIGUSR1']:
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
async def request_data(
    request: Request,
    data_request: DataRequest,
    cache: aioredis.client.Redis = Depends(redis_dependency),
):
        cache_key = data_request._key
        cached_result = await cache.get(cache_key)
        if cached_result is not None:
            request_uuid = cached_result.decode('utf-8')
        else:
            task = perform_fetch_task.apply_async(args=(data_request.dict(),))
            request_uuid = task.id
            # expires 5 minutes before the result expires for celery
            expire_time = result_expires - timedelta(minutes=5)
            await cache.set(
                cache_key,
                request_uuid.encode('utf-8'),
                ex=int(expire_time.total_seconds()),
            )
        return {
            "status": "success",
            "job_uuid": str(request_uuid),
            "result_url": f"/data/job/{str(request_uuid)}",
            "msg": f"Job {str(request_uuid)} created.",
        }
    # try:
    #     cache_key = data_request._key
    #     cached_result = await cache.get(cache_key)
    #     if cached_result is not None:
    #         request_uuid = cached_result.decode('utf-8')
    #     else:
    #         task = perform_fetch_task.apply_async(args=(data_request.dict(),))
    #         request_uuid = task.id
    #         # expires 5 minutes before the result expires for celery
    #         expire_time = result_expires - timedelta(minutes=5)
    #         await cache.set(
    #             cache_key,
    #             request_uuid.encode('utf-8'),
    #             ex=int(expire_time.total_seconds()),
    #         )
    #     return {
    #         "status": "success",
    #         "job_uuid": str(request_uuid),
    #         "result_url": f"/data/job/{str(request_uuid)}",
    #         "msg": f"Job {str(request_uuid)} created.",
    #     }
    # except Exception as e:
    #     return JSONResponse(
    #         content={
    #             "status": "failed",
    #             "job_uuid": None,
    #             "result_url": None,
    #             "msg": f"Error occured: {e}",
    #         },
    #         status_code=500,
    #     )
