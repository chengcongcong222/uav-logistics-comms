"""DEM terrain occlusion for radio LOS (no link-budget formulas here)."""
from __future__ import annotations

import numpy as np
from rasterio.transform import rowcol

from src.common.terrain import Dem


def _los_height(z1: float, z2: float, lam: float) -> float:
    return (1.0 - lam) * z1 + lam * z2


def blocked_line_cells(
    dem: Dem,
    x1: float,
    y1: float,
    z1: float,
    x2: float,
    y2: float,
    z2: float,
) -> bool:
    """PRIMARY: raster line traversal. True if terrain blocks LOS.

    Endpoints (their cells) are excluded from occlusion tests (open segment).
    Horizontal coords are lon/lat (EPSG:4326) matching DEM grid.
    """
    # convert lon/lat to row/col via same transform as Dem
    r1, c1 = rowcol(dem.transform, x1, y1)
    r2, c2 = rowcol(dem.transform, x2, y2)
    r1, c1, r2, c2 = int(r1), int(c1), int(r2), int(c2)

    # Bresenham cells along segment
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

    endpoint_cells = {(r1, c1), (r2, c2)}
    # also drop first/last few identical cells
    unique_interior = []
    seen = set()
    for cell in cells:
        if cell in endpoint_cells or cell in seen:
            continue
        seen.add(cell)
        unique_interior.append(cell)

    if not unique_interior:
        return False

    n = len(cells)
    for idx, (r, c) in enumerate(cells):
        if (r, c) in endpoint_cells:
            continue
        if r < 0 or c < 0 or r >= dem.arr.shape[0] or c >= dem.arr.shape[1]:
            return True  # out of DEM = treat blocked
        # lambda from position along cells (approx)
        lam = (idx + 0.5) / max(n - 1, 1)
        lam = min(max(lam, 0.0), 1.0)
        z_los = _los_height(z1, z2, lam)
        z_dem = float(dem.arr[r, c])
        if dem.nodata is not None and z_dem == dem.nodata:
            continue
        if z_dem >= z_los:
            return True
    return False


def blocked_dense_sample(
    dem: Dem,
    x1: float,
    y1: float,
    z1: float,
    x2: float,
    y2: float,
    z2: float,
    step_m: float = 10.0,
) -> bool:
    """INDEPENDENT: dense sampling along horizontal path (does not call cell walker)."""
    # approximate meters per degree
    mid_lat = 0.5 * (y1 + y2)
    m_per_deg_lat = 111320.0
    m_per_deg_lon = 111320.0 * max(0.05, np.cos(np.deg2rad(mid_lat)))
    dx_m = (x2 - x1) * m_per_deg_lon
    dy_m = (y2 - y1) * m_per_deg_lat
    dist_h = float(np.hypot(dx_m, dy_m))
    n = max(2, int(dist_h / max(step_m, 1.0)) + 1)
    for i in range(1, n):
        lam = i / n  # strictly interior samples only
        lon = x1 + lam * (x2 - x1)
        lat = y1 + lam * (y2 - y1)
        z_los = _los_height(z1, z2, lam)
        try:
            z_dem = dem.sample(float(lon), float(lat))
        except ValueError:
            return True
        if z_dem >= z_los:
            return True
    return False


def is_blocked(dem: Dem, a: tuple[float, float, float], b: tuple[float, float, float]) -> bool:
    return blocked_line_cells(dem, a[0], a[1], a[2], b[0], b[1], b[2])
