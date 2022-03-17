from typing import Any, Dict
import asyncio
import functools
import msgpack

from loguru import logger

from app.core.celery_app import celery_app
from celery.exceptions import SoftTimeLimitExceeded
from .data_fetcher import fetch
from app.cache.redis import redis_dependency
from app.models import DataRequest


def sync(f):
    """Decorater to make async to sync for a solo pool within celery worker"""
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        return asyncio.get_event_loop().run_until_complete(f(*args, **kwargs))

    return wrapper


@celery_app.task(bind=True)
@sync
async def perform_fetch_task(
    self,
    data_request: Dict[str, Any],
):
    cache = await redis_dependency()
    data_request_object = DataRequest(**data_request)
    cache_key = data_request_object._key
    cached_result = await cache.get(cache_key)

    try:
        request_params = data_request["ref"].split(",")
        download = data_request.get('download', False)
        # TODO: For now use z as color, need to change in future, esp for 3D
        axis_params = {
            "x": data_request['x'],
            "y": data_request['y'],
            "z": data_request['color'],
        }

        download_format = data_request.get('download_format', 'netcdf4')
        if not download_format:
            download_format = 'netcdf4'

        job_type = "download" if download else "plot"
        status_dict = {
            "status": "started",
            "result": data_request,
            "type": job_type,
            "msg": "Data retrieval started.",
        }
        self.update_state(
            state="PROGRESS",
            meta=status_dict,
        )
        start_dt = data_request['start_dt']
        end_dt = data_request['end_dt']
        if cached_result is not None:
            logger.info("Using cached result.")
            status_dict.update({"msg": "Using cached data."})
            self.update_state(state="PROGRESS", meta=status_dict)
            result = msgpack.unpackb(cached_result)
            logger.info("Result done.")
        else:
            logger.info("Fetching new result.")
            result = fetch(
                self,
                request_params,
                axis_params,
                start_dt,
                end_dt,
                download,
                download_format,
                status_dict,
            )
            # Cache the result for 1 hour
            await cache.set(cache_key, msgpack.packb(result), ex=3600)
        if result is not None:
            if job_type == "download" and result["file_url"] is None:
                return {
                    "status": "completed",
                    "result": None,
                    "msg": result["msg"],
                }
            else:
                return {
                    "status": "completed",
                    "result": result,
                    "msg": "Result finished.",
                }
        else:
            return {
                "status": "completed",
                "result": None,
                "msg": f"No data found for {start_dt} to {end_dt}",  # noqa
            }
    except SoftTimeLimitExceeded:
        return {
            "status": "cancelled",
            "result": None,
            "msg": "Job was cancelled by user.",
        }
