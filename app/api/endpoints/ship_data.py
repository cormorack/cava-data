import logging
import json
from enum import Enum

import dask.dataframe as dd

import pandas as pd

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from starlette.requests import Request

from ...core.config import settings


logger = logging.getLogger(__name__)
logging.root.setLevel(level=logging.INFO)

router = APIRouter()
FS = settings.FILE_SYSTEMS['aws_s3']
SHIP_S3_MAP = {
    'profile': f"s3://{settings.CADAI_BUCKET}/{settings.SHIP_DATA_PROFILES}",
    'discrete': f"s3://{settings.CADAI_BUCKET}/{settings.SHIP_DATA_DISCRETE}",
}

with FS.open(f'{settings.CADAI_BUCKET}/{settings.SHIP_DATA_LABEL_MAP}') as f:
    LABEL_MAP = json.load(f)


class ShipDataTypes(str, Enum):
    profile = "profile"
    discrete = "discrete"


@router.get("/")
def ship_data_details():
    with FS.open(f'{settings.CADAI_BUCKET}/{settings.SHIP_DATA_SOURCE}') as f:
        source_json = json.load(f)
    return {
        "profiles_location": SHIP_S3_MAP['profile'],
        "discrete_location": SHIP_S3_MAP['discrete'],
        "data_sources": source_json,
    }


@router.get("/labels/")
async def fetch_ship_data_labels():
    return LABEL_MAP


@router.get("/labels/{name}")
async def fetch_ship_data_label_detail(name: str):
    if name in LABEL_MAP:
        return LABEL_MAP[name]
    else:
        return {"msg": f"{name} not found."}


@router.get("/{data_type}")
async def fetch_ship_data(data_type: ShipDataTypes):
    valid_types = ['profile', 'discrete']
    if data_type.value in valid_types:
        df = dd.read_parquet(SHIP_S3_MAP[data_type]).compute()
        df_json = json.loads(df.to_json(orient='records'))
        return {"status": "success", "result": df_json, "msg": ""}
    else:
        return {
            "status": "error",
            "result": None,
            "msg": f"{data_type} is invalid. Valid values: {', '.join(valid_types)}",
        }
