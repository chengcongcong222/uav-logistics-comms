"""Hierarchical relay candidate site generation (E5)."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
from pyproj import Transformer
from rasterio.transform import rowcol

from src.common.schemas import EPSG_UTM49N, EPSG_WGS84
from src.q3.link_budget import distance_m, fspl_db, load_comm_params, margin_db, pair_lmax, path_loss_db
from src.q3.relay_geometry import evaluate_relay_site, load_relay_params
from src.q3.terrain_los import blocked_line_cells

TF = Transformer.from_crs(EPSG_UTM49N, EPSG_WGS84, always_xy=True)
TF_INV = Transformer.from_crs(EPSG_WGS84, EPSG_UTM49N, always_xy=True)


def site_id_of(x, y, z) -> str:
    return f"R{int(round(x)):d}_{int(round(y)):d}_{int(round(z)):d}"


def make_site(dem, x, y, agl, setup_s=30.0, service_s=10.0):
    lon, lat = TF.transform(x, y)
    ground = dem.sample(lon, lat)
    z = ground + agl
    if not (0.0 < agl <= 300.0):
        return None
    return {
        "site_id": site_id_of(x, y, z),
        "x_m": x,
        "y_m": y,
        "lon": lon,
        "lat": lat,
        "ground_elevation_m": ground,
        "agl_m": agl,
        "z_amsl_m": z,
    }


def backhaul_margin(dem, params, l_max_rg, site) -> tuple[float, float, bool]:
    from src.q3.relay_geometry import o01_pos

    ox, oy, oz = o01_pos()
    # G01 is +20m AGL
    import json

    from src.common.paths import PROCESSED_DIR

    raw = json.loads((PROCESSED_DIR / "communication_parameters.json").read_text(encoding="utf-8"))
    h_g = float(raw["endpoints"]["固定网关 G01"]["天线离地高度（m）"]["value"])
    g01 = (ox, oy, oz + h_g)
    o_ll = TF.transform(ox, oy)
    g_ll = (o_ll[0], o_ll[1], g01[2])
    r_ll = (site["lon"], site["lat"], site["z_amsl_m"])
    d = distance_m((site["x_m"], site["y_m"], site["z_amsl_m"]), g01)
    blocked = blocked_line_cells(dem, r_ll[0], r_ll[1], r_ll[2], g_ll[0], g_ll[1], g_ll[2])
    mc = margin_db(l_max_rg, path_loss_db(params, d, blocked))
    return mc, d, blocked


def access_margin(dem, params, l_max_tr, site, tpos_utm) -> tuple[float, bool, float]:
    r_ll = (site["lon"], site["lat"], site["z_amsl_m"])
    t_ll = TF.transform(tpos_utm[0], tpos_utm[1])
    d = distance_m(tpos_utm, (site["x_m"], site["y_m"], site["z_amsl_m"]))
    blocked = blocked_line_cells(dem, t_ll[0], t_ll[1], tpos_utm[2], r_ll[0], r_ll[1], r_ll[2])
    mc = margin_db(l_max_tr, path_loss_db(params, d, blocked))
    return mc, blocked, d


def hierarchical_sites(dem, cx, cy, radius_m: float, setup_s: float, service_s: float, only_step: float | None = None):
    """Yield site dicts on one grid level (or all if only_step is None)."""
    heights = [50, 100, 150, 200, 250, 300]
    seen = set()
    steps = (only_step,) if only_step else (120.0, 60.0, 30.0)
    for step in steps:
        n = max(1, int(radius_m / step))
        xs = cx + np.arange(-n, n + 1) * step
        ys = cy + np.arange(-n, n + 1) * step
        for x in xs:
            for y in ys:
                for agl in heights:
                    s = make_site(dem, float(x), float(y), agl, setup_s, service_s)
                    if s is None or s["site_id"] in seen:
                        continue
                    seen.add(s["site_id"])
                    s["grid_step_m"] = step
                    yield s


def refine_heights(site_xy, dem, setup_s, service_s):
    for agl in range(25, 301, 25):
        s = make_site(dem, site_xy[0], site_xy[1], float(agl), setup_s, service_s)
        if s:
            yield s
