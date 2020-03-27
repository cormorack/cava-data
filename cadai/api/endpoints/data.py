import logging
import uuid
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from starlette.requests import Request

from ...store import JOB_RESULTS
from ..utils import get_ds
from ...models import DataRequest
from .utils.helpers import perform_fetch
from .download import router as download_router

logger = logging.getLogger(__name__)
logging.root.setLevel(level=logging.INFO)

router = APIRouter()
router.include_router(
    download_router, prefix="/download",
)


# ------------------ API ROUTES --------------------------------
@router.get("/")
def list_datasets():
    return get_ds()


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
