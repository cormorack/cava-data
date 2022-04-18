import logging
import json
from enum import Enum

import dask.dataframe as dd

from fastapi import APIRouter, Depends

from ...core.config import settings


logger = logging.getLogger(__name__)
logging.root.setLevel(level=logging.INFO)

router = APIRouter()


async def get_s3fs():
    return settings.FILE_SYSTEMS['aws_s3']


async def get_label_map(filesystem=Depends(get_s3fs)):
    with filesystem.open(f'{settings.CADAI_BUCKET}/{settings.SHIP_DATA_LABEL_MAP}') as f:
        return json.load(f)

SHIP_S3_MAP = {
    'profile': f"s3://{settings.CADAI_BUCKET}/{settings.SHIP_DATA_PROFILES}",
    'discrete': f"s3://{settings.CADAI_BUCKET}/{settings.SHIP_DATA_DISCRETE}",
}


class ShipDataTypes(str, Enum):
    profile = "profile"
    discrete = "discrete"


@router.get("/")
def ship_data_details(filesystem=Depends(get_s3fs)):
    with filesystem.open(f'{settings.CADAI_BUCKET}/{settings.SHIP_DATA_SOURCE}') as f:
        source_json = json.load(f)
    return {
        "profiles_location": SHIP_S3_MAP['profile'],
        "discrete_location": SHIP_S3_MAP['discrete'],
        "data_sources": source_json,
    }


@router.get("/labels/")
async def fetch_ship_data_labels(label_map=Depends(get_label_map)):
    return label_map


@router.get("/labels/{name}")
async def fetch_ship_data_label_detail(name: str, label_map=Depends(get_label_map)):
    if name in label_map:
        return label_map[name]
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
