import threading
import logging
import os
import numpy as np
from functools import reduce
from dask import dataframe
import datashader as ds
import numba
import xarray as xr

from ...store import DATASETS_STORE, JOB_RESULTS

MAX_POINTS = 500000
startdt = np.datetime64("1900-01-01")

logger = logging.getLogger(__name__)
logging.root.setLevel(level=logging.INFO)


# ------------------ Helper Functions ------------------------
def fetch_ds(dataset_id, start_dt, end_dt, parameters):
    xrd = DATASETS_STORE[dataset_id]
    dataset = xrd.dataset

    partds = dataset.sel(time=slice(start_dt, end_dt))
    cols = [c for c in partds.data_vars if c in parameters]
    return partds[cols]


def perform_shading(df, axis_params, start_date, end_date, high_res=False):
    if "time" not in axis_params.values():
        df.drop("time", axis=1)
    # Datashading
    if axis_params["x"] == "time":
        # x_range = (
        #     df[axis_params["x"]].min().compute(),
        #     df[axis_params["x"]].max().compute(),
        # )
        x_range = (start_date, end_date)
    else:
        x_range = (df[axis_params["x"]].min(), df[axis_params["x"]].max())
        # x_range = ranges[axis_params["x"]]

    # y_range = ranges[axis_params["y"]]
    y_range = (df[axis_params["y"]].min(), df[axis_params["y"]].max())

    # res = (2560, 1440)
    res = (540, 260)
    if high_res:
        res = (3840, 2160)
    cvs = ds.Canvas(
        x_range=x_range, y_range=y_range, plot_height=res[1], plot_width=res[0]
    )
    if axis_params["z"]:
        agg = cvs.points(
            df, axis_params["x"], axis_params["y"], agg=ds.mean(axis_params["z"])
        )
    else:
        agg = cvs.points(
            df, axis_params["x"], axis_params["y"], agg=ds.mean(axis_params["y"])
        )

    x = _nan_to_nulls(agg[axis_params["x"]].values)
    y = _nan_to_nulls(agg[axis_params["y"]].values)
    z = _nan_to_nulls(agg.values)
    return x, y, z


def _nan_to_nulls(values):
    arr = np.nan_to_num(values, nan=-999999)
    return np.where(arr == -999999, None, arr)


def get_seconds_since(time):
    return (
        get_timedelta(startdt, np.datetime64(time))
        .astype("timedelta64[s]")
        .astype("int64")
    )


@numba.jit(nopython=True)
def get_date(date, delta):
    return date + delta


@numba.jit(nopython=True)
def get_timedelta(date1, date2):
    return date2 - date1


class DataFetcher:
    """ Threading example class
    The run() method will be started and it will run in the background
    until the application exits.
    """

    def __init__(
        self,
        uuid,
        request_params,
        axis_params,
        start_dt,
        end_dt,
        download=False,
        download_format="netcdf",
    ):
        """ Constructor
        :type interval: int
        :param interval: Check interval, in seconds
        """
        self._uuid = uuid
        self._request_params = request_params
        self._axis_params = axis_params
        self._start_dt = start_dt
        self._end_dt = end_dt
        self._download = download
        self._download_format = download_format

        if self._download:
            import fsspec

            self._fs = fsspec.filesystem("s3")
            self._bucket = "io2data-test"
            self._out_name = "__".join(
                [v for v in sorted(set(axis_params.values())) if v]
                + [self._start_dt, self._end_dt]
            )
            self._s3_fold = f"{self._bucket}/downloads/"

        # Setup parameters
        self._parameters = []
        self.setup_params()

        self._in_progress = True

        thread = threading.Thread(target=self.run, args=())
        thread.daemon = True  # Daemonize thread
        thread.start()  # Start the execution

    def setup_params(self):
        parameters = [v for v in set(self._axis_params.values()) if v]
        if "time" not in parameters:
            parameters = parameters + ["time"]

        self._parameters = parameters

    def run(self):
        """ Method that runs forever """
        while self._in_progress:
            logger.info("Request Started.")
            job_type = "download" if self._download else "plot"
            JOB_RESULTS[self._uuid] = {
                "status": "started",
                "result": None,
                "type": job_type,
                "msg": f"Job {self._uuid} started.",
            }
            try:
                JOB_RESULTS[self._uuid].update({"msg": "Retrieving data from store..."})
                data_list, data_count = self._retrieve_data_list()
                if not self._download:
                    self._request_plot_data(data_list, data_count)
                else:
                    self._request_download_data(data_list, data_count)
            except Exception as e:
                JOB_RESULTS[self._uuid].update(
                    {"status": "failed", "msg": f"Data retrieval failed: {e}"}
                )

                logger.warning(f"Result failed: {e}")
            self._in_progress = False

    def _nc_creator(self, mds, file_path):
        mds.to_netcdf(file_path, engine="netcdf4")

    def _csv_creator(self, mds, file_path):
        mds.to_dataframe().to_csv(file_path)

    def _json_creator(self, mds, file_path):
        mds.to_dataframe().reset_index().to_json(file_path, orient="records")

    def _file_creator(self, mds, ext=".nc"):
        file_name = self._out_name + ext
        file_path = "/tmp/" + file_name
        s3_path = self._s3_fold + file_name
        creators = {
            ".nc": self._nc_creator,
            ".csv": self._csv_creator,
            ".json": self._json_creator,
        }
        JOB_RESULTS[self._uuid].update(
            {"status": "in-progress", "msg": "Compiling data..."}
        )
        if not self._fs.exists(s3_path):
            logger.info(f"Writing to local file: {file_path}")
            # Use one of the creator above
            creators[ext](mds, file_path)

            # Upload to s3
            if os.path.exists(file_path):
                logger.info(f"Uploading to s3: {s3_path}")
                self._fs.put(file_path, s3_path)
                os.unlink(file_path)
            else:
                raise FileNotFoundError(f"{file_path} does not exists.")
        else:
            logger.info(f"{s3_path} exists.")

        JOB_RESULTS[self._uuid].update(
            {
                "status": "completed",
                "result": f"https://{self._bucket}.s3-us-west-2.amazonaws.com/downloads/{file_name}",
                "msg": f"File download url created.",
            }
        )

    def _request_download_data(self, data_list, data_count):
        mds = self._fetch_and_merge(data_list)
        if len(mds.time) == 0:
            JOB_RESULTS[self._uuid].update(
                {
                    "status": "completed",
                    "result": None,
                    "msg": f"No data found for {self._start_dt} to {self._end_dt}",
                }
            )
        else:
            if self._download_format == "netcdf":
                self._file_creator(mds, ext=".nc")
            elif self._download_format == "csv":
                self._file_creator(mds, ext=".csv")
            elif self._download_format == "json":
                self._file_creator(mds, ext=".json")
            else:
                raise TypeError(f"{self._download_format} is not a valid download format.")

        logger.info("Download completed.")

    def _create_new_attrs(self, mds, sample):
        from collections import OrderedDict
        import datetime

        new_attrs = OrderedDict()
        new_attrs["acknowledgement"] = sample["summary"]
        new_attrs["creator_name"] = sample["creator_name"]
        new_attrs["creator_url"] = sample["creator_url"]
        new_attrs["date_created"] = sample["date_created"]
        new_attrs["date_downloaded"] = datetime.datetime.now().isoformat()
        new_attrs["notes"] = sample["Notes"]
        new_attrs["owner"] = sample["Owner"]
        new_attrs["source_refs"] = ",".join(self._request_params)
        new_attrs["time_coverage_start"] = np.datetime_as_string(mds.time.min())
        new_attrs["time_coverage_end"] = np.datetime_as_string(mds.time.max())
        new_attrs["uuid"] = str(self._uuid)

        return new_attrs

    def _fetch_and_merge(self, data_list):
        JOB_RESULTS[self._uuid].update(
            {"status": "in-progress", "msg": "Creating merged dataset..."}
        )
        dflist = self._get_dflist(data_list)

        if len(dflist) > 1:
            mds = self._merge_datasets(dflist)
        else:
            mds = dflist[0]

        if len(mds.time) > 0:
            new_attrs = self._create_new_attrs(mds, dflist[0].attrs)
            mds.attrs = new_attrs

        return mds

    def _request_plot_data(self, data_list, data_count):
        mds = self._fetch_and_merge(data_list)
        if len(mds.time) == 0:
            JOB_RESULTS[self._uuid].update(
                {
                    "status": "completed",
                    "result": None,
                    "msg": f"No data found for {self._start_dt} to {self._end_dt}",
                }
            )
        else:
            mds["time"] = mds.time.astype(np.int64)
            final_df = mds.to_dask_dataframe()

            # Shading process
            if data_count > MAX_POINTS:
                JOB_RESULTS[self._uuid].update(
                    {"msg": "Performing datashading and serializing results..."}
                )
                x, y, z = perform_shading(
                    final_df,
                    self._axis_params,
                    start_date=get_seconds_since(self._start_dt),
                    end_date=get_seconds_since(self._end_dt),
                )
                shaded = True
            else:
                JOB_RESULTS[self._uuid].update({"msg": "Serializing result..."})
                x = _nan_to_nulls(final_df[self._axis_params["x"]].values.compute())
                y = _nan_to_nulls(final_df[self._axis_params["y"]].values.compute())
                if self._axis_params["z"]:
                    z = _nan_to_nulls(final_df[self._axis_params["z"]].values.compute())
                else:
                    z = np.array([])
                shaded = False

            if self._axis_params["x"] == "time":
                x = np.array([self._seconds_to_date(time).astype(str) for time in x])

            result = (
                {
                    "x": x.tolist(),
                    "y": y.tolist(),
                    "z": z.tolist(),
                    "count": data_count,
                    "shaded": shaded,
                },
            )
            JOB_RESULTS[self._uuid].update(
                {"status": "completed", "result": result, "msg": "Result finished.",}
            )

        logger.info("Result done.")

    def _retrieve_data_list(self):
        data_list = {}
        highest_count = 0
        for dataset_id in self._request_params:
            dataset = fetch_ds(
                dataset_id, self._start_dt, self._end_dt, self._parameters
            )
            count = len(dataset.time)
            # if not self._download:
            #     # Convert to int for now for easier merge
            #     dataset["time"] = dataset.time.astype(np.int64)
            #     data_list[dataset_id] = {
            #         "data": dataset.to_dask_dataframe(),
            #         "count": count,
            #     }
            # else:
            #     data_list[dataset_id] = {"data": dataset, "count": count}

            data_list[dataset_id] = {"data": dataset, "count": count}

            if count > highest_count:
                highest_count = count
        return data_list, highest_count

    def _get_dflist(self, data_list):
        sorted_keys = sorted(
            data_list, key=lambda x: data_list[x]["count"], reverse=True
        )
        highest_key = sorted_keys[0]
        dflist = []
        for idx, k in enumerate(sorted_keys):
            if idx == 0:
                res = data_list[k]["data"]
            else:
                res = data_list[k]["data"].reindex_like(
                    data_list[highest_key]["data"], method="nearest", tolerance="1s"
                )
            dflist.append(res)

        return dflist

    def _merge_datasets(self, dflist):
        mergedds = xr.merge(dflist).unify_chunks()

        # Delete old chunks
        for k, v in mergedds.variables.items():
            del v.encoding["chunks"]

        # Rechunk the data
        return mergedds.chunk({"time": 1024 ** 2})

    def _merge_dataframes(self, dflist, tol=5000000000):
        final_df = reduce(
            lambda left, right: dataframe.multi.merge_asof(
                left, right, on="time", direction="nearest", tolerance=tol
            ),
            dflist,
        )
        return final_df

    def _seconds_to_date(self, time):
        delta = np.timedelta64(np.int64(time * 1000 * 1000), "us")
        return get_date(startdt, delta)
