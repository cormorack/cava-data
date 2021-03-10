import uuid
import logging
from ...workers import DataFetcher

logger = logging.getLogger(__name__)
logging.root.setLevel(level=logging.INFO)


def perform_fetch(data_request, download=False):
    request_params = data_request.ref.split(",")
    # TODO: For now use z as color, need to change in future, esp for 3D
    axis_params = {"x": data_request.x, "y": data_request.y, "z": data_request.color}
    request_uuid = uuid.uuid4()
    download_format = data_request.download_format

    DataFetcher(
        request_uuid,
        request_params,
        axis_params,
        data_request.start_dt,
        data_request.end_dt,
        download,
        download_format,
    )

    return request_uuid
