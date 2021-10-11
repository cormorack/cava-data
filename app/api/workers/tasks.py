from app.core.celery_app import celery_app
from celery.exceptions import SoftTimeLimitExceeded
from .data_fetcher import fetch


@celery_app.task(bind=True)
def perform_fetch_task(self, data_request):
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
        start_dt = data_request['start_dt']
        end_dt = data_request['end_dt']
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
