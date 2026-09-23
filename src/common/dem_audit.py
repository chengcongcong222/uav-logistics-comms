"""E1 DEM audit: compare .mat and .tif, write metadata and elevation checks."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
from scipy.io import loadmat

from src.common.coordinates import lonlat_to_utm49n
from src.common.paths import DEM_MAT, DEM_TIF, PROCESSED_DIR, RESULTS_E1
from src.common.schemas import EPSG_UTM49N, EPSG_WGS84


def load_tif() -> dict:
    with rasterio.open(DEM_TIF) as ds:
        arr = ds.read(1)
        nodata = ds.nodata
        transform = ds.transform
        crs = ds.crs.to_string() if ds.crs else None
        bounds = ds.bounds
        meta = {
            "rows": ds.height,
            "cols": ds.width,
            "crs": crs,
            "transform": list(transform)[:6],
            "res_x": abs(transform.a),
            "res_y": abs(transform.e),
            "nodata": nodata,
            "bounds": {
                "left": bounds.left,
                "bottom": bounds.bottom,
                "right": bounds.right,
                "top": bounds.top,
            },
            "dtype": str(arr.dtype),
        }
    valid = arr if nodata is None else arr[arr != nodata]
    if nodata is not None:
        valid = arr[arr != nodata]
    meta["min_elev"] = float(np.min(valid)) if valid.size else None
    meta["max_elev"] = float(np.max(valid)) if valid.size else None
    meta["has_nodata"] = bool(np.any(arr == nodata)) if nodata is not None else False
    # north-up if transform.e < 0 (row 0 is north)
    meta["row0_is_north"] = bool(transform.e < 0)
    return {**meta, "array": arr, "nodata": nodata, "transform": transform}


def load_mat() -> dict:
    raw = loadmat(DEM_MAT)
    keys = [k for k in raw.keys() if not k.startswith("__")]
    out = {"keys": keys}
    # discover main elevation matrix
    elev_key = None
    for k in keys:
        v = raw[k]
        if isinstance(v, np.ndarray) and v.ndim == 2 and v.size > 1000:
            elev_key = k
            break
    if elev_key is None:
        raise RuntimeError(f"No elevation matrix found in MAT; keys={keys}")
    elev = np.asarray(raw[elev_key], dtype=float)
    out["elev_key"] = elev_key
    out["shape"] = list(elev.shape)
    out["min_elev"] = float(np.nanmin(elev))
    out["max_elev"] = float(np.nanmax(elev))
    out["array"] = elev
    # optional georef vectors
    for k in keys:
        v = raw[k]
        if isinstance(v, np.ndarray) and v.size <= 5000 and k != elev_key:
            out.setdefault("aux", {})[k] = {
                "shape": list(np.asarray(v).shape),
                "sample": np.asarray(v).ravel()[:5].tolist(),
            }
    return out


def sample_dem_lonlat(tif_meta: dict, lon: float, lat: float) -> float | None:
    from rasterio.transform import rowcol

    arr = tif_meta["array"]
    transform = tif_meta["transform"]
    nodata = tif_meta["nodata"]
    # TIF is EPSG:4326: sample with lon/lat directly
    r, c = rowcol(transform, lon, lat)
    if r < 0 or c < 0 or r >= arr.shape[0] or c >= arr.shape[1]:
        return None
    val = float(arr[r, c])
    if nodata is not None and val == nodata:
        return None
    return val


def main() -> None:
    tif = load_tif()
    mat = load_mat()

    # MAT vs TIF consistency on shape/elev range (orientation may differ)
    shape_match = tuple(mat["shape"]) == (tif["rows"], tif["cols"]) or tuple(mat["shape"]) == (
        tif["cols"],
        tif["rows"],
    )
    min_diff = abs(mat["min_elev"] - tif["min_elev"])
    max_diff = abs(mat["max_elev"] - tif["max_elev"])
    elev_match = min_diff < 1e-3 and max_diff < 1e-3

    # orientation: compare flipped variants numerically against tif sample if shapes allow
    orientation = "unknown"
    mat_arr = mat["array"]
    tif_arr = tif["array"]
    if mat_arr.shape == tif_arr.shape:
        if np.allclose(mat_arr, tif_arr, equal_nan=True):
            orientation = "row0_matches_tif_row0"
        elif np.allclose(mat_arr[::-1, :], tif_arr, equal_nan=True):
            orientation = "row0_is_south_flipped_to_match_tif"
        elif np.allclose(mat_arr.T, tif_arr, equal_nan=True):
            orientation = "transposed_match"
        else:
            orientation = "same_shape_values_differ"
    elif mat_arr.shape == tif_arr.T.shape:
        if np.allclose(mat_arr, tif_arr.T, equal_nan=True):
            orientation = "mat_is_transposed_tif"
        else:
            orientation = "transposed_shape_values_differ"
    else:
        orientation = f"shape_mismatch mat={mat_arr.shape} tif={tif_arr.shape}"

    dem_metadata = {
        "epsg_lonlat": EPSG_WGS84,
        "epsg_plane": EPSG_UTM49N,
        "tif": {
            "rows": tif["rows"],
            "cols": tif["cols"],
            "crs": tif["crs"],
            "res_x_m": tif["res_x"],
            "res_y_m": tif["res_y"],
            "bounds": tif["bounds"],
            "nodata": tif["nodata"],
            "has_nodata": tif["has_nodata"],
            "min_elev_m": tif["min_elev"],
            "max_elev_m": tif["max_elev"],
            "row0_is_north": tif["row0_is_north"],
        },
        "mat": {
            "elev_key": mat["elev_key"],
            "shape": mat["shape"],
            "min_elev_m": mat["min_elev"],
            "max_elev_m": mat["max_elev"],
            "aux_keys": list(mat.get("aux", {}).keys()),
        },
        "consistency": {
            "shape_match_or_transpose": shape_match,
            "elev_range_match": elev_match,
            "orientation": orientation,
        },
    }
    (PROCESSED_DIR / "dem_metadata.json").write_text(
        json.dumps(dem_metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # node elevation cross-check
    nodes = pd.read_csv(PROCESSED_DIR / "nodes.csv")
    rows = []
    for _, n in nodes.iterrows():
        dem_elev = sample_dem_lonlat(tif, float(n["longitude"]), float(n["latitude"]))
        given = float(n["ground_elevation_m"])
        diff = None if dem_elev is None else given - dem_elev
        rows.append(
            {
                "node_id": n["node_id"],
                "node_type": n["node_type"],
                "longitude": n["longitude"],
                "latitude": n["latitude"],
                "x_m": n["x_m"],
                "y_m": n["y_m"],
                "given_elevation_m": given,
                "dem_elevation_m": dem_elev,
                "difference_m": diff,
            }
        )
    elev_df = pd.DataFrame(rows)
    elev_df.to_csv(RESULTS_E1 / "node_dem_elevation_check.csv", index=False)

    audit = pd.DataFrame(
        [
            {"item": "tif_rows", "value": tif["rows"]},
            {"item": "tif_cols", "value": tif["cols"]},
            {"item": "tif_res_x_m", "value": tif["res_x"]},
            {"item": "tif_res_y_m", "value": tif["res_y"]},
            {"item": "tif_crs", "value": tif["crs"]},
            {"item": "tif_min_elev", "value": tif["min_elev"]},
            {"item": "tif_max_elev", "value": tif["max_elev"]},
            {"item": "tif_row0_is_north", "value": tif["row0_is_north"]},
            {"item": "mat_shape", "value": str(mat["shape"])},
            {"item": "mat_min_elev", "value": mat["min_elev"]},
            {"item": "mat_max_elev", "value": mat["max_elev"]},
            {"item": "orientation", "value": orientation},
            {"item": "shape_match_or_transpose", "value": shape_match},
            {"item": "elev_range_match", "value": elev_match},
            {
                "item": "node_elev_diff_abs_mean",
                "value": float(elev_df["difference_m"].abs().mean()),
            },
            {
                "item": "node_elev_diff_abs_max",
                "value": float(elev_df["difference_m"].abs().max()),
            },
        ]
    )
    audit.to_csv(RESULTS_E1 / "dem_audit.csv", index=False)
    print("DEM_AUDIT_WRITTEN")
    print(audit.to_string(index=False))


if __name__ == "__main__":
    main()
