"""Coordinate transforms: keep lon/lat, derive UTM 49N meters."""
from __future__ import annotations

from pyproj import CRS, Transformer

from .schemas import EPSG_UTM49N, EPSG_WGS84

_tf = Transformer.from_crs(CRS.from_epsg(EPSG_WGS84), CRS.from_epsg(EPSG_UTM49N), always_xy=True)


def lonlat_to_utm49n(lon: float, lat: float) -> tuple[float, float]:
    x, y = _tf.transform(lon, lat)
    return x, y


def utm49n_valid(lon: float, lat: float) -> bool:
    # UTM 49N: 108°E–114°E, northern hemisphere
    return (108.0 <= lon <= 114.0) and (0.0 <= lat <= 84.0)
