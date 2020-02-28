from cadai.store import DATASETS_STORE


def get_ds():
    return [
        {"zarr_url": v.zarr_url, "dataset_id": v.dataset_id, "path": v.prefix}
        for k, v in DATASETS_STORE.items()
    ]
