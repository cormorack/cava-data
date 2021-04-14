import threading
import logging
import os
import gc
import sys
import traceback
import numpy as np
from functools import reduce
import dask.dataframe as dd
import dask.array as da
import datashader as ds
import numba
import xarray as xr
import pandas as pd
import intake
import zarr
import fsspec
import hvplot.xarray
from ...core.config import settings

from ...store import DATASETS_STORE, JOB_RESULTS

MAX_POINTS = 500000
startdt = np.datetime64("1900-01-01")

logger = logging.getLogger(__name__)
logging.root.setLevel(level=logging.INFO)


# ------------------ Helper Functions ------------------------
def _filter_time(dataset, start_dt, end_dt):
    arr = dataset.time.data
    idx_arr = np.where(
        (arr >= pd.to_datetime(start_dt).to_datetime64())
        & (arr <= pd.to_datetime(end_dt).to_datetime64())
    )[0]
    return dataset.isel(time=idx_arr)


def fetch_ds(dataset_id, start_dt, end_dt, parameters):
    xrd = DATASETS_STORE[dataset_id]
    dataset = xrd.dataset

    partds = _filter_time(dataset, start_dt, end_dt)
    cols = [c for c in partds.data_vars if c in parameters]
    return partds[cols]


def perform_shading(df, axis_params, start_date, end_date, high_res=False):
    # if "time" not in axis_params.values():
    #     df.drop("time", axis=1)
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

    if axis_params["z"]:
        plot = df.hvplot.scatter(
            x=axis_params["x"],
            y=axis_params["y"],
            color=axis_params["z"],
            rasterize=True,
            width=res[0],
            height=res[1],
        )
    else:
        plot = df.hvplot.scatter(
            x=axis_params["x"],
            y=axis_params["y"],
            color=axis_params["z"],
            rasterize=True,
            width=res[0],
            height=res[1],
            aggregator=ds.mean(axis_params["y"])
        )
    agg = plot[()].data
    # cvs = ds.Canvas(
    #     x_range=x_range, y_range=y_range, plot_height=res[1], plot_width=res[0]
    # )
    # if axis_params["z"]:
    #     agg = cvs.points(
    #         df,
    #         axis_params["x"],
    #         axis_params["y"],
    #         agg=ds.mean(axis_params["z"]),
    #     )
    # else:
    #     agg = cvs.points(
    #         df,
    #         axis_params["x"],
    #         axis_params["y"],
    #         agg=ds.mean(axis_params["y"]),
    #     )

    if axis_params["x"] == "time":
        x = agg[axis_params["x"]].data.astype(str)
    else:
        x = _nan_to_nulls(agg[axis_params["x"]].data)
    y = _nan_to_nulls(agg[axis_params["y"]].data)
    if axis_params["z"]:
        z = _nan_to_nulls(agg[f"{axis_params['x']}_{axis_params['y']} {axis_params['z']}"].data)  # noqa
    else:
        z = _nan_to_nulls(agg[f"{axis_params['x']}_{axis_params['y']} {axis_params['y']}"].data)  # noqa
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


def setup_params(axis_params):
    parameters = [v for v in set(axis_params.values()) if v]
    if "time" not in parameters:
        parameters = parameters + ["time"]

    return parameters


def _fetch_ds(dataset_id, start_dt, end_dt, parameters):
    zarr_mapper = fsspec.get_mapper(
        f"s3://{settings.DATA_BUCKET}/{dataset_id}", anon=True
    )
    zg = zarr.open_consolidated(zarr_mapper)
    drop_vars = [a for a in zg.array_keys() if a not in parameters]
    dataset = xr.open_dataset(
        zarr_mapper,
        chunks='auto',
        engine='zarr',
        backend_kwargs={'consolidated': True},
        drop_variables=drop_vars,
    )

    partds = dataset.sel(time=slice(start_dt, end_dt))

    del dataset
    del zg
    gc.collect()
    return partds


def retrieve_data_list(request_params, start_dt, end_dt, parameters):
    data_list = {}
    highest_count = 0
    for dataset_id in request_params:
        dataset = _fetch_ds(dataset_id, start_dt, end_dt, parameters)
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


def _get_dflist(data_list):
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
                data_list[highest_key]["data"],
                method="nearest",
                tolerance="1s",
            )
        dflist.append(res)

    return dflist


def _merge_datasets(dflist):
    mergedds = xr.merge(dflist).unify_chunks()
    return mergedds


def _seconds_to_date(time):
    pdt = pd.to_datetime(time)
    # delta = np.timedelta64(np.int64(time * 1000 * 1000), "us")
    # return get_date(startdt, delta)
    return pdt.to_numpy()


def fetch_zarr(zarr_url, storage_options={'anon': True}):
    zg = zarr.open_consolidated(
        fsspec.get_mapper(zarr_url, **storage_options), mode='r'
    )
    dimensions = {}
    variable_arrays = {}
    for k, a in zg.arrays():
        if k in a.attrs['_ARRAY_DIMENSIONS']:
            dimensions[k] = a.attrs['_ARRAY_DIMENSIONS']
        else:
            variable_arrays[k] = a.attrs['_ARRAY_DIMENSIONS']
    return zg, dimensions, variable_arrays


def search_values(arr, start=None, end=None, equal=None):
    if start:
        indices = da.where(arr >= start)
    elif end:
        indices = da.where(arr <= end)
    elif equal:
        indices = da.where(arr == equal)

    if start and end:
        indices = da.where(da.logical_and(arr >= start, arr <= end))

    return indices[0].compute()


def fetch(
    self,
    request_params,
    axis_params,
    start_dt,
    end_dt,
    download,
    download_format,
    status_dict,
):
    self.update_state(
        state="PROGRESS",
        meta=status_dict,
    )
    parameters = setup_params(axis_params)
    if "time" not in parameters:
        parameters.append("time")

    status_dict.update({"msg": "Retrieving data from store..."})
    self.update_state(state="PROGRESS", meta=status_dict)

    data_list, data_count = retrieve_data_list(
        request_params, start_dt, end_dt, parameters
    )
    status_dict.update({"msg": "Reindexing datasets..."})
    dflist = _get_dflist(data_list)
    status_dict.update({"msg": "Merging datasets..."})
    mds = _merge_datasets(dflist)

    if len(mds.time) == 0:
        result = None
    else:
        # mds["time"] = mds.time.astype(np.int64)
        # final_df = mds.to_dask_dataframe()

        # Shading process
        if data_count > MAX_POINTS:
            status_dict.update(
                {"msg": "Performing datashading and serializing results..."}
            )
            self.update_state(state="PROGRESS", meta=status_dict)
            x, y, z = perform_shading(
                mds,
                axis_params,
                start_date=get_seconds_since(start_dt),
                end_date=get_seconds_since(end_dt),
            )
            shaded = True
        else:
            status_dict.update({"msg": "Serializing result..."})
            self.update_state(state="PROGRESS", meta=status_dict)
            if axis_params["x"] == "time":
                x = mds[axis_params["x"]].data.astype(str)
            else:
                x = _nan_to_nulls(mds[axis_params["x"]].data.compute())
            y = _nan_to_nulls(mds[axis_params["y"]].data.compute())
            if axis_params["z"]:
                z = _nan_to_nulls(mds[axis_params["z"]].data.compute())
            else:
                z = np.array([])
            shaded = False

        result = (
            {
                "x": x.tolist(),
                "y": y.tolist(),
                "z": z.tolist(),
                "count": data_count,
                "shaded": shaded,
            },
        )
    logger.info("Result done.")
    return result


class DataFetcher:
    """
    Python Object to fetch and filter data stream
    TODO: THIS OBJECT NEED IMPROVEMENTS ...
    """

    def __init__(
        self,
        zarr_url,
        storage_options={'anon': True},
        chunksize=int(50 * (1024 ** 2)),
        parameters=[],
    ):
        self._zarr_url = zarr_url
        self._chunksize = chunksize
        self._storage_options = storage_options
        self._parameters = parameters

        self._coords = {}
        self._data_vars = {}
        self._selections = {}
        self._selection_results = {}
        self._ranges = {}
        self.dataframe = None

        self._setup()

    def _setup(self):
        zarr_group, dimensions, variable_arrays = fetch_zarr(
            self._zarr_url, storage_options=self._storage_options
        )

        for k, v in dimensions.items():
            self._coords[k] = (
                tuple(v),
                da.from_array(zarr_group[k], chunks=self._chunksize),
            )

        for k, v in variable_arrays.items():
            if k in self._parameters:
                self._data_vars[k] = (
                    tuple(v),
                    da.from_array(zarr_group[k], chunks=self._chunksize),
                )

        self._chunk_index_maps = {
            k: self.__get_chunk_index_map(v[1])
            for k, v in self._coords.items()
        }

    def sel(self, **kwargs):
        for k, v in kwargs.items():
            if k not in self._coords:
                print(f"{k} not a dimension!")
            else:
                self._selections[k] = v

        self.__perform_selections()
        all_cols, ordered_dims, expand_dims = self.__set_results()

        # Create dask dataframe
        # series_list = []
        # for name, v in all_cols.items():
        #     self._ranges[name] = (v[1][0], v[1][-1])
        #     if name in expand_dims:
        #         var = xr.Variable(dims=(), data=v[1])
        #     else:
        #         var = xr.Variable(
        #             dims=[i for i in v[0] if i in ordered_dims], data=v[1]
        #         )
        #     dask_array = var.set_dims(ordered_dims).chunk(self._chunksize).data
        #     series = dd.from_array(dask_array.reshape(-1), columns=[name])
        #     series_list.append(series)

        # self.dataframe = dd.concat(series_list, axis=1)
        # return self.dataframe

        return xr.Dataset(
            coords=self.final_coords, data_vars=self.final_data_vars
        )

    def __perform_selections(self):
        for k, v in self._selections.items():
            self._selection_results[k] = self.__filter_arr_indices(
                self._coords[k][1],
                chunk_index_map=self._chunk_index_maps[k],
                query=v,
            )

    def __set_results(self):
        all_cols = {}
        ordered_dims = {}
        expand_dims = []
        self.final_coords = {}
        self.final_data_vars = {}
        if all(v for v in self._selection_results.values()):
            for k, v in self._coords.items():
                dims = v[0]
                vda = v[1]
                data_filter = []
                for d in dims:
                    selection = self._selection_results[d]
                    if isinstance(selection, list):
                        data_filter.append(slice(selection[0], selection[-1]))
                    else:
                        data_filter.append(selection)

                filtered = vda[tuple(data_filter)]

                if filtered.shape:
                    ordered_dims[k] = filtered.shape[0]
                else:
                    expand_dims.append(k)

                all_cols[k] = (dims, filtered)
                self.final_coords[k] = (dims, filtered)

            for k, v in self._data_vars.items():
                dims = v[0]
                vda = v[1]
                data_filter = []
                for d in dims:
                    selection = self._selection_results[d]
                    if isinstance(selection, list):
                        data_filter.append(slice(selection[0], selection[-1]))
                    else:
                        data_filter.append(selection)
                filtered = vda[tuple(data_filter)]
                all_cols[k] = (dims, filtered)
                self.final_data_vars[k] = (dims, filtered)

        return all_cols, ordered_dims, expand_dims

    @staticmethod
    def __get_chunk_index_map(zda):
        last_index = 0
        chunk_index_map = {}
        for idx, b in enumerate(zda.partitions):
            chunksize = b.chunksize[0]
            chunk_index_map[idx] = last_index
            if last_index != 0:
                last_index = last_index + chunksize
            else:
                last_index = chunksize
        return chunk_index_map

    @staticmethod
    def __filter_arr_indices(zda, chunk_index_map, query):

        start = None
        end = None
        equal = None

        if isinstance(query, tuple):
            query = slice(*query)

        if isinstance(query, slice):
            start = query.start
            end = query.stop
        else:
            equal = query

        indices = search_values(zda, start=start, end=end, equal=equal)

        final = list(set(indices))
        if len(final) == 1:
            return final[0]
        else:
            return final


# class DataFetcher:
#     """ Threading example class
#     The run() method will be started and it will run in the background
#     until the application exits.
#     """

#     def __init__(
#         self,
#         uuid,
#         request_params,
#         axis_params,
#         start_dt,
#         end_dt,
#         download=False,
#         download_format="netcdf",
#     ):
#         """ Constructor
#         :type interval: int
#         :param interval: Check interval, in seconds
#         """
#         self._uuid = uuid
#         self._request_params = request_params
#         self._axis_params = axis_params
#         self._start_dt = start_dt
#         self._end_dt = end_dt
#         self._download = download
#         self._download_format = download_format

#         if self._download:
#             import fsspec

#             self._fs = fsspec.filesystem("s3")
#             self._bucket = "ooi-data-cadai"
#             self._out_name = "__".join(
#                 [v for v in sorted(set(axis_params.values())) if v]
#                 + [self._start_dt, self._end_dt]
#             )
#             self._s3_fold = f"{self._bucket}/downloads/"

#         # Setup parameters
#         self._parameters = []
#         self.setup_params()

#         self._in_progress = True

#         thread = threading.Thread(target=self.run, args=())
#         thread.daemon = True  # Daemonize thread
#         thread.start()  # Start the execution

#     def setup_params(self):
#         parameters = [v for v in set(self._axis_params.values()) if v]
#         if "time" not in parameters:
#             parameters = parameters + ["time"]

#         self._parameters = parameters

#     def run(self):
#         """ Method that runs forever """
#         while self._in_progress:
#             logger.info("Request Started.")
#             job_type = "download" if self._download else "plot"
#             JOB_RESULTS[self._uuid] = {
#                 "status": "started",
#                 "result": None,
#                 "type": job_type,
#                 "msg": f"Job {self._uuid} started.",
#             }
#             try:
#                 JOB_RESULTS[self._uuid].update(
#                     {"msg": "Retrieving data from store..."}
#                 )
#                 data_list, data_count = self._retrieve_data_list()
#                 if not self._download:
#                     self._request_plot_data(data_list, data_count)
#                 else:
#                     self._request_download_data(data_list, data_count)
#             except Exception as e:
#                 exc_info = sys.exc_info()
#                 message = "".join(traceback.format_exception(*exc_info))
#                 JOB_RESULTS[self._uuid].update(
#                     {"status": "failed", "msg": f"Data retrieval failed: {e}"}
#                 )

#                 logger.warning(f"Result failed: {message}")
#             self._in_progress = False

#     def _nc_creator(self, mds, file_path):
#         mds.to_netcdf(file_path, engine="netcdf4")

#     def _csv_creator(self, mds, file_path):
#         mds.to_dataframe().to_csv(file_path)

#     def _json_creator(self, mds, file_path):
#         mds.to_dataframe().reset_index().to_json(file_path, orient="records")

#     def _file_creator(self, mds, ext=".nc"):
#         file_name = self._out_name + ext
#         file_path = "/tmp/" + file_name
#         s3_path = self._s3_fold + file_name
#         creators = {
#             ".nc": self._nc_creator,
#             ".csv": self._csv_creator,
#             ".json": self._json_creator,
#         }
#         JOB_RESULTS[self._uuid].update(
#             {"status": "in-progress", "msg": "Compiling data..."}
#         )
#         if not self._fs.exists(s3_path):
#             logger.info(f"Writing to local file: {file_path}")
#             # Use one of the creator above
#             creators[ext](mds, file_path)

#             # Upload to s3
#             if os.path.exists(file_path):
#                 logger.info(f"Uploading to s3: {s3_path}")
#                 self._fs.put(file_path, s3_path)
#                 os.unlink(file_path)
#             else:
#                 raise FileNotFoundError(f"{file_path} does not exists.")
#         else:
#             logger.info(f"{s3_path} exists.")

#         JOB_RESULTS[self._uuid].update(
#             {
#                 "status": "completed",
#                 "result": f"https://{self._bucket}.s3-us-west-2.amazonaws.com/downloads/{file_name}",
#                 "msg": f"File download url created.",
#             }
#         )

#     def _request_download_data(self, data_list, data_count):
#         mds = self._fetch_and_merge(data_list)
#         if len(mds.time) == 0:
#             JOB_RESULTS[self._uuid].update(
#                 {
#                     "status": "completed",
#                     "result": None,
#                     "msg": f"No data found for {self._start_dt} to {self._end_dt}",
#                 }
#             )
#         else:
#             if self._download_format == "netcdf":
#                 self._file_creator(mds, ext=".nc")
#             elif self._download_format == "csv":
#                 self._file_creator(mds, ext=".csv")
#             elif self._download_format == "json":
#                 self._file_creator(mds, ext=".json")
#             else:
#                 raise TypeError(
#                     f"{self._download_format} is not a valid download format."
#                 )

#         logger.info("Download completed.")

#     def _create_new_attrs(self, mds, sample):
#         from collections import OrderedDict
#         import datetime

#         new_attrs = OrderedDict()
#         new_attrs["acknowledgement"] = sample["summary"]
#         new_attrs["creator_name"] = sample["creator_name"]
#         new_attrs["creator_url"] = sample["creator_url"]
#         new_attrs["date_created"] = sample["date_created"]
#         new_attrs["date_downloaded"] = datetime.datetime.now().isoformat()
#         new_attrs["notes"] = sample["Notes"]
#         new_attrs["owner"] = sample["Owner"]
#         new_attrs["source_refs"] = ",".join(self._request_params)
#         new_attrs["time_coverage_start"] = np.datetime_as_string(
#             mds.time.min()
#         )
#         new_attrs["time_coverage_end"] = np.datetime_as_string(mds.time.max())
#         new_attrs["uuid"] = str(self._uuid)

#         return new_attrs

#     def _fetch_and_merge(self, data_list):
#         JOB_RESULTS[self._uuid].update(
#             {"status": "in-progress", "msg": "Creating merged dataset..."}
#         )
#         dflist = self._get_dflist(data_list)

#         if len(dflist) > 1:
#             mds = self._merge_datasets(dflist)
#         else:
#             mds = dflist[0]

#         if len(mds.time) > 0:
#             new_attrs = self._create_new_attrs(mds, dflist[0].attrs)
#             mds.attrs = new_attrs

#         return mds

#     def _request_plot_data(self, data_list, data_count):
#         mds = self._fetch_and_merge(data_list)
#         if len(mds.time) == 0:
#             JOB_RESULTS[self._uuid].update(
#                 {
#                     "status": "completed",
#                     "result": None,
#                     "msg": f"No data found for {self._start_dt} to {self._end_dt}",
#                 }
#             )
#         else:
#             mds["time"] = mds.time.astype(np.int64)
#             final_df = mds.to_dask_dataframe()

#             # Shading process
#             if data_count > MAX_POINTS:
#                 JOB_RESULTS[self._uuid].update(
#                     {
#                         "msg": "Performing datashading and serializing results..."
#                     }
#                 )
#                 x, y, z = perform_shading(
#                     final_df,
#                     self._axis_params,
#                     start_date=get_seconds_since(self._start_dt),
#                     end_date=get_seconds_since(self._end_dt),
#                 )
#                 shaded = True
#             else:
#                 JOB_RESULTS[self._uuid].update(
#                     {"msg": "Serializing result..."}
#                 )
#                 x = _nan_to_nulls(
#                     final_df[self._axis_params["x"]].values.compute()
#                 )
#                 y = _nan_to_nulls(
#                     final_df[self._axis_params["y"]].values.compute()
#                 )
#                 if self._axis_params["z"]:
#                     z = _nan_to_nulls(
#                         final_df[self._axis_params["z"]].values.compute()
#                     )
#                 else:
#                     z = np.array([])
#                 shaded = False

#             if self._axis_params["x"] == "time":
#                 x = np.array(
#                     [self._seconds_to_date(time).astype(str) for time in x]
#                 )

#             result = (
#                 {
#                     "x": x.tolist(),
#                     "y": y.tolist(),
#                     "z": z.tolist(),
#                     "count": data_count,
#                     "shaded": shaded,
#                 },
#             )
#             JOB_RESULTS[self._uuid].update(
#                 {
#                     "status": "completed",
#                     "result": result,
#                     "msg": "Result finished.",
#                 }
#             )

#         logger.info("Result done.")

#     def _retrieve_data_list(self):
#         data_list = {}
#         highest_count = 0
#         for dataset_id in self._request_params:
#             dataset = fetch_ds(
#                 dataset_id, self._start_dt, self._end_dt, self._parameters
#             )
#             count = len(dataset.time)
#             # if not self._download:
#             #     # Convert to int for now for easier merge
#             #     dataset["time"] = dataset.time.astype(np.int64)
#             #     data_list[dataset_id] = {
#             #         "data": dataset.to_dask_dataframe(),
#             #         "count": count,
#             #     }
#             # else:
#             #     data_list[dataset_id] = {"data": dataset, "count": count}

#             data_list[dataset_id] = {"data": dataset, "count": count}

#             if count > highest_count:
#                 highest_count = count
#         return data_list, highest_count

#     def _get_dflist(self, data_list):
#         sorted_keys = sorted(
#             data_list, key=lambda x: data_list[x]["count"], reverse=True
#         )
#         highest_key = sorted_keys[0]
#         dflist = []
#         for idx, k in enumerate(sorted_keys):
#             if idx == 0:
#                 res = data_list[k]["data"]
#             else:
#                 res = data_list[k]["data"].reindex_like(
#                     data_list[highest_key]["data"],
#                     method="nearest",
#                     tolerance="1s",
#                 )
#             dflist.append(res)

#         return dflist

#     def _merge_datasets(self, dflist):
#         mergedds = xr.merge(dflist).unify_chunks()

#         # Delete old chunks
#         for k, v in mergedds.variables.items():
#             del v.encoding["chunks"]

#         # Rechunk the data
#         return mergedds.chunk({"time": 1024 ** 2})

#     def _merge_dataframes(self, dflist, tol=5000000000):
#         final_df = reduce(
#             lambda left, right: dataframe.multi.merge_asof(
#                 left, right, on="time", direction="nearest", tolerance=tol
#             ),
#             dflist,
#         )
#         return final_df

#     def _seconds_to_date(self, time):
#         pdt = pd.to_datetime(time)
#         # delta = np.timedelta64(np.int64(time * 1000 * 1000), "us")
#         # return get_date(startdt, delta)
#         return pdt.to_numpy()
