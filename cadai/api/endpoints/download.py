import logging
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from starlette.requests import Request

from ...store import JOB_RESULTS
from ...models import DataRequest
from .utils.helpers import perform_fetch


logger = logging.getLogger(__name__)
logging.root.setLevel(level=logging.INFO)

router = APIRouter()


@router.get("/")
def download_details():
    return {"formats_available": ["csv", "json", "netcdf"]}


@router.post("/", status_code=202)
def request_download(request: Request, data_request: DataRequest):
    try:
        request_uuid = perform_fetch(data_request, download=True)

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
