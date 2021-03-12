from app.core.celery_app import celery_app
import time


@celery_app.task
def test_celery(word: str) -> str:
    return f"test task return {word}"


@celery_app.task(bind=True)
def perform_fetch_task(self, data_request):
    request_params = data_request["ref"].split(",")
    download = data_request["download"]
    # TODO: For now use z as color, need to change in future, esp for 3D
    axis_params = {
        "x": data_request['x'],
        "y": data_request['y'],
        "z": data_request['color'],
    }
    download_format = data_request['download_format']

    # TODO: Modify fetching to function not Object?
    # DataFetcher(
    #     request_uuid,
    #     request_params,
    #     axis_params,
    #     data_request.start_dt,
    #     data_request.end_dt,
    #     download,
    #     download_format,
    # )
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

    time.sleep(1)
    status_dict.update({"msg": "Retrieving data from store..."})
    self.update_state(state="PROGRESS", meta=status_dict)

    time.sleep(1)
    status_dict.update(
        {"msg": "Performing datashading and serializing results..."}
    )
    self.update_state(state="PROGRESS", meta=status_dict)

    time.sleep(5)
    status_dict.update({"msg": "Serializing result..."})
    self.update_state(state="PROGRESS", meta=status_dict)

    time.sleep(10)
    result = (
        {
            "x": [],
            "y": [],
            "z": [],
            "count": 0,
            "shaded": False,
        },
    )
    return {
        "status": "completed",
        "result": result,
        "msg": "Result finished.",
    }
