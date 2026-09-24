"""O01 <-> arbitrary relay hover geometry and relay energy (E5)."""
from __future__ import annotations

import math

import pandas as pd

from src.common.paths import PROCESSED_DIR
from src.common.transport_energy import climb_energy_kwh, descent_energy_kwh
from src.common.terrain import Dem
from src.common.schemas import CRUISE_MARGIN_ABOVE_MAX_DEM_M
from src.q3.link_budget import distance_m

G0 = 9.80665
KWH_FROM_JOULE = 3.6e6


def load_relay_params() -> dict:
    t = pd.read_csv(PROCESSED_DIR / "relay_uav_types.csv").iloc[0]
    return {
        "takeoff_mass_kg": float(t.takeoff_mass_kg),
        "cruise_speed_mps": float(t.cruise_speed_mps),
        "cruise_power_kw": float(t.cruise_power_kw),
        "energy_kwh": float(t.energy_kwh),
        "rho": float(t.return_soc_min_pct) / 100.0,
        "prep_time_s": float(t.prep_time_s),
        "setup_time_s": float(t.link_setup_time_s),
        "turnaround_time_s": float(t.turnaround_time_s),
        "max_climb_mps": float(t.max_climb_mps),
        "max_descend_mps": float(t.max_descend_mps),
        "climb_eff": float(t.climb_energy_eff),
        "descend_eff": float(t.descend_energy_eff),
        "hover_power_kw": float(t.hover_power_kw),
        "comm_power_kw": float(t.comm_power_kw),
        "max_agl_m": float(t.max_hover_agl_m),
    }


def o01_pos(nodes: pd.DataFrame | None = None) -> tuple[float, float, float]:
    if nodes is None:
        nodes = pd.read_csv(PROCESSED_DIR / "nodes.csv").set_index("node_id")
    n = nodes.loc["O01"]
    return float(n.x_m), float(n.y_m), float(n.ground_elevation_m)


def leg_profile(dem: Dem, x1, y1, z1, x2, y2, z2, lonlat1, lonlat2):
    """Return horizontal dist, max DEM along route (lon/lat), cruise alt, climb1, climb2, desc1, desc2."""
    # sample DEM along lon/lat segment
    n = max(2, int(math.hypot(x2 - x1, y2 - y1) / 30.0) + 1)
    max_dem = -1e9
    for i in range(n + 1):
        u = i / n
        lon = lonlat1[0] + u * (lonlat2[0] - lonlat1[0])
        lat = lonlat1[1] + u * (lonlat2[1] - lonlat1[1])
        max_dem = max(max_dem, dem.sample(float(lon), float(lat)))
    d_h = math.hypot(x2 - x1, y2 - y1)
    h_cruise = max(max_dem + CRUISE_MARGIN_ABOVE_MAX_DEM_M, z1, z2)
    climb = max(0.0, h_cruise - z1)
    desc = max(0.0, h_cruise - z2)
    return d_h, max_dem, h_cruise, climb, desc


def relay_route_energy_time(
    params: dict,
    d_h: float,
    climb_out: float,
    desc_out: float,
    climb_back: float,
    desc_back: float,
    setup_s: float,
    service_s: float,
) -> dict:
    m = params["takeoff_mass_kg"]
    vc = params["cruise_speed_mps"]
    vu = params["max_climb_mps"]
    vd = params["max_descend_mps"]
    t_hor = d_h / vc
    t_out = climb_out / vu + t_hor + desc_out / vd
    t_back = climb_back / vu + t_hor + desc_back / vd
    e_hor = params["cruise_power_kw"] * (2 * t_hor) / 3600.0
    e_up = climb_energy_kwh(climb_out + climb_back, m, params["climb_eff"])
    e_dn = descent_energy_kwh(desc_out + desc_back, m, params["descend_eff"])
    p_hover_comm = params["hover_power_kw"] + params["comm_power_kw"]
    e_setup = p_hover_comm * setup_s / 3600.0
    e_service = p_hover_comm * service_s / 3600.0
    e_flight = e_hor + e_up + e_dn
    e_total = e_flight + e_setup + e_service
    e_use = params["energy_kwh"]
    margin = (1.0 - params["rho"]) * e_use - e_total
    return {
        "outbound_time_s": t_out,
        "return_time_s": t_back,
        "horizontal_time_s": 2 * t_hor,
        "flight_energy_kwh": e_flight,
        "setup_energy_kwh": e_setup,
        "service_energy_kwh": e_service,
        "total_energy_kwh": e_total,
        "energy_margin_kwh": margin,
        "return_soc": 1.0 - e_total / e_use,
        "climb_out_m": climb_out,
        "climb_back_m": climb_back,
        "desc_out_m": desc_out,
        "desc_back_m": desc_back,
        "cruise_alt_m": None,  # filled by caller if needed
    }


def evaluate_relay_site(dem: Dem, params: dict, R_utm, R_ll, setup_s: float, service_s: float) -> dict:
    ox, oy, oz = o01_pos()
    from pyproj import Transformer
    from src.common.schemas import EPSG_UTM49N, EPSG_WGS84

    tf = Transformer.from_crs(EPSG_UTM49N, EPSG_WGS84, always_xy=True)
    o_ll = tf.transform(ox, oy)
    d_h, max_dem, h_cruise, c1, d1 = leg_profile(dem, ox, oy, oz, R_utm[0], R_utm[1], R_utm[2], o_ll, R_ll)
    # back: from hover to O01 (outbound reverse geometry)
    d_h2, max_dem2, h_cruise2, c2, d2 = leg_profile(
        dem, R_utm[0], R_utm[1], R_utm[2], ox, oy, oz, R_ll, o_ll
    )
    # use max cruise of both directions for safety
    h_c = max(h_cruise, h_cruise2)
    c1 = max(0.0, h_c - oz)
    d1 = max(0.0, h_c - R_utm[2])
    c2 = max(0.0, h_c - R_utm[2])
    d2 = max(0.0, h_c - oz)
    en = relay_route_energy_time(params, d_h, c1, d1, c2, d2, setup_s, service_s)
    en["horizontal_distance_m"] = d_h
    en["max_dem_on_route_m"] = max(max_dem, max_dem2)
    en["cruise_alt_m"] = h_c
    return en
