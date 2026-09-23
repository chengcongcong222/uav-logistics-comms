"""Terrain/DEM access for route profiles (lon/lat grid, row0=north)."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import rowcol

from .paths import DEM_TIF, PROCESSED_DIR


class Dem:
    def __init__(self) -> None:
        with rasterio.open(DEM_TIF) as ds:
            self.arr = ds.read(1).astype(float)
            self.transform = ds.transform
            self.crs = ds.crs
            self.nodata = ds.nodata
            self.bounds = ds.bounds
        self.meta = json.loads((PROCESSED_DIR / "dem_metadata.json").read_text(encoding="utf-8"))

    def sample(self, lon: float, lat: float) -> float:
        r, c = rowcol(self.transform, lon, lat)
        if r < 0 or c < 0 or r >= self.arr.shape[0] or c >= self.arr.shape[1]:
            raise ValueError(f"lon/lat outside DEM: {lon},{lat}")
        val = float(self.arr[r, c])
        if self.nodata is not None and val == self.nodata:
            raise ValueError(f"DEM nodata at {lon},{lat}")
        return val

    def max_along_segment(self, lon1: float, lat1: float, lon2: float, lat2: float, n_samples: int | None = None) -> float:
        """Raster line crossing / dense sample of DEM max along the lon-lat segment."""
        # dense sampling independent path used for cross-check when n_samples set
        if n_samples is None:
            # Bresenham-like via many samples along the line (core method)
            n_samples = max(2, int(np.hypot((lon2 - lon1) * 111000, (lat2 - lat1) * 111000) / 30) + 1)
        lons = np.linspace(lon1, lon2, n_samples)
        lats = np.linspace(lat1, lat2, n_samples)
        vals = [self.sample(float(x), float(y)) for x, y in zip(lons, lats)]
        return float(np.max(vals))

    def max_along_segment_cells(self, lon1: float, lat1: float, lon2: float, lat2: float) -> float:
        """Independent method: walk unique raster cells crossed by the segment."""
        r1, c1 = rowcol(self.transform, lon1, lat1)
        r2, c2 = rowcol(self.transform, lon2, lat2)
        # integer line (Bresenham)
        cells = []
        dr = abs(r2 - r1)
        dc = abs(c2 - c1)
        sr = 1 if r1 < r2 else -1
        sc = 1 if c1 < c2 else -1
        err = dr - dc
        r, c = r1, c1
        while True:
            cells.append((r, c))
            if r == r2 and c == c2:
                break
            e2 = 2 * err
            if e2 > -dc:
                err -= dc
                r += sr
            if e2 < dr:
                err += dr
                c += sc
        vals = []
        for r, c in cells:
            if 0 <= r < self.arr.shape[0] and 0 <= c < self.arr.shape[1]:
                vals.append(float(self.arr[r, c]))
        return float(np.max(vals)) if vals else float("nan")
