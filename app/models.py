import json
import hashlib

from pydantic import BaseModel, PrivateAttr
from typing import Optional


class DataRequest(BaseModel):
    ref: str
    x: str
    y: str
    start_dt: str
    end_dt: str
    z: str = ""
    color: str = ""
    download_format: str = "netcdf"
    download: bool = False

    _key: str = PrivateAttr()

    def __init__(self, **data):
        super().__init__(**data)
        self._set_key()

    def _set_key(self):
        encoded_json = json.dumps(self.dict()).encode('utf-8')
        md5_hash = hashlib.md5(encoded_json)
        self._key = md5_hash.hexdigest()


class CancelConfig(BaseModel):
    signal: Optional[str] = 'SIGUSR1'
