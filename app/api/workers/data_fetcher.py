import logging
import numpy as np
import xarray as xr
import zarr
import fsspec
import hvplot.xarray  # noqa
from .models import OOIDataset

logger = logging.getLogger(__name__)
logging.root.setLevel(level=logging.INFO)


# ------------------ Helper Functions ------------------------
def _nan_to_nulls(values):
    """Converts nan to null values"""
    arr = np.nan_to_num(values, nan=-999999)
    return np.where(arr == -999999, None, arr)


def setup_params(axis_params):
    parameters = [v for v in set(axis_params.values()) if v]
    if "time" not in parameters:
        parameters = parameters + ["time"]

    return parameters


def _merge_datasets(data_list, axis_params):
    """Merges all dataset in data_list together into a single one"""
    # Merge data_list
    dslist = []

    # --- This way of merging is for simple data only! ---
    sorted_keys = sorted(
        data_list, key=lambda x: len(data_list[x].time), reverse=True
    )

    highest = sorted_keys[0]
    for idx, k in enumerate(sorted_keys):
        if idx == 0:
            res = data_list[k]
        else:
            res = data_list[k].reindex_like(
                data_list[highest],
                method="nearest",
                tolerance="1s",
            )
        dslist.append(res)
    # --- Done one way of merging ---

    merged = xr.merge(dslist, combine_attrs="no_conflicts").unify_chunks()

    # Swapping dimensions for plotting to work if time is not
    # an axis selection
    if axis_params["x"] != "time":
        merged = merged.swap_dims({"time": axis_params['x']})

    return merged


def _plot_merged_dataset(
    merged: xr.Dataset,
    axis_params: dict,
    shade_threshold: int = 500000,
    plot_size: tuple = (888, 450),
) -> dict:
    """Use hvplot to plot the dataset and parse the plot dataframe"""

    def _change_z(k):
        if k == 'z':
            return 'color'
        return k

    rasterize = True if len(merged.time) > shade_threshold else False

    plot_params = {_change_z(k): v for k, v in axis_params.items()}
    color_column = (
        f"{plot_params['x']}_{plot_params['y']} {plot_params['color']}"
    )

    plot = merged.hvplot.scatter(
        rasterize=rasterize,
        width=plot_size[0],
        height=plot_size[1],
        **plot_params,
    )

    df = plot[()].dframe()
    if "time" in df:
        df.loc[:, "time"] = df["time"].astype(str)

    if plot_params["color"]:
        final_df = df.rename(columns={color_column: plot_params['color']})
    else:
        final_df = df[[v for k, v in plot_params.items() if v]]

    final_dct = final_df.to_dict(orient='list')
    final_dct = {
        var: _nan_to_nulls(values).tolist()
        for var, values in final_dct.items()
    }

    return final_dct, rasterize


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

    # TODO: Need to add other parameters for multidimensional
    # need a check for nutnr,pco2,ph,optaa add int_ctd_pressure
    # parameters.append("int_ctd_pressure")

    # for spikr
    # parameters.append("spectra")

    status_dict.update({"msg": "Retrieving data from store..."})
    self.update_state(state="PROGRESS", meta=status_dict)
    data_list = {}
    for dataset_id in request_params:
        ooids = OOIDataset(dataset_id)[parameters].sel(time=(start_dt, end_dt))
        data_list[dataset_id] = ooids.dataset

    status_dict.update({"msg": "Reindexing and merging datasets..."})
    self.update_state(state="PROGRESS", meta=status_dict)
    merged = _merge_datasets(data_list, axis_params)
    data_count = len(merged.time)

    if data_count == 0:
        result = None
    else:
        # Shading process
        final_dct, shaded = _plot_merged_dataset(merged, axis_params)
        x = final_dct.get(axis_params['x'], [])
        y = final_dct.get(axis_params['y'], [])
        z = []
        if axis_params['z']:
            z = final_dct.get(axis_params['z'], np.array([]))

        result = (
            {
                "x": x,
                "y": y,
                "z": z,
                "count": data_count,
                "shaded": shaded,
            },
        )
    logger.info("Result done.")
    # ================ End Compute results ========================
    return result
