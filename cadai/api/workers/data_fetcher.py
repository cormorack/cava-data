import threading
import logging
import numpy as np
from functools import reduce
from dask import dataframe
import datashader as ds
import numba

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

    def _request_download_data(self, data_list, data_count):
        # TODO: Need to implement data download
        import time

        JOB_RESULTS[self._uuid].update(
            {"status": "in-progress", "msg": "Compiling data..."}
        )
        time.sleep(10)
        JOB_RESULTS[self._uuid].update(
            {
                "status": "completed",
                "result": "https://path.to.file",
                "msg": f"Download finished. Format: {self._download_format}",
            }
        )

        logger.info("Download completed.")

    def _request_plot_data(self, data_list, data_count):
        JOB_RESULTS[self._uuid].update(
            {"status": "in-progress", "msg": "Creating dask dataframes..."}
        )
        dflist = self._get_dflist(data_list)
        if len(dflist) > 1:
            JOB_RESULTS[self._uuid].update(
                {"msg": "Merging and finalizing dask dataframes..."}
            )
            final_df = self._merge_dataframes(dflist)
        else:
            JOB_RESULTS[self._uuid].update({"msg": "Finalizing dask dataframes..."})
            final_df = dflist[0]

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
            if not self._download:
                # Convert to int for now for easier merge
                dataset["time"] = dataset.time.astype(np.int64)
                data_list[dataset_id] = {
                    "data": dataset.to_dask_dataframe(),
                    "count": count,
                }
            else:
                data_list[dataset_id] = {"data": dataset, "count": count}

            if count > highest_count:
                highest_count = count
        return data_list, highest_count

    def _get_dflist(self, data_list):
        sorted_keys = sorted(
            data_list, key=lambda x: data_list[x]["count"], reverse=True
        )
        return [data_list[k]["data"] for k in sorted_keys]

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
