import os

import xarray as xr
import xpublish  # noqa

from pydantic import BaseModel
from .core.config import FILE_SYSTEMS


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


class XRDataset:
    def __init__(self, zarr_url, mounted=False):
        self._zarr_url = zarr_url
        self._mounted = mounted
        self._dataset_id = ""
        self._ds = None
        self._fs = FILE_SYSTEMS['aws_s3']

        self.setup()

    @property
    def zarr_url(self):
        return self._zarr_url

    @property
    def dataset_id(self):
        return self._dataset_id

    @property
    def is_mountable(self):
        return self._mounted

    @property
    def router(self):
        if isinstance(self._ds, xr.Dataset):
            return self._ds.rest.app.router

    @property
    def app(self):
        if isinstance(self._ds, xr.Dataset):
            if self._mounted:
                self._ds.rest(
                    app_kws=dict(
                        title=self._dataset_id,
                        openapi_prefix=f"/{self._dataset_id}",
                    )
                )
            return self._ds.rest.app

    @property
    def dataset(self):
        return self._ds

    @property
    def prefix(self):
        return f"/{self._dataset_id}"

    def __repr__(self):
        return f"<XRDataset: {self._dataset_id}>"

    def setup(self):
        self._dataset_id = os.path.basename(self._zarr_url)
        if ".zarr" in self._dataset_id:
            self._dataset_id = self._dataset_id.replace(".zarr", "")

    def set_ds(self, ds=None):
        if isinstance(ds, xr.Dataset):
            self._ds = ds
        elif ds is None:
            self._ds = xr.open_zarr(
                self._fs.get_mapper(self._zarr_url), consolidated=True
            )
            for k, v in self._ds.variables.items():
                if 'chunks' in v.encoding:
                    del v.encoding['chunks']
