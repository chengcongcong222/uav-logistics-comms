"""Adaptive sampling + binary refinement + gap extraction."""
from __future__ import annotations

import math

import pandas as pd

from src.q3.communication_margin import margin_transport_g01
from src.q3.link_budget import load_comm_params


def sample_flight_segment(p0, p1, max_h_m: float = 15.0, max_v_m: float = 5.0) -> list[tuple[float, float, float, float]]:
    """Return samples (t_frac, x, y, z) in [0,1] along segment with adaptive steps."""
    x0, y0, z0, _ = p0
    x1, y1, z1, _ = p1
    # approximate meters
    mid_lat = 0.5 * (y0 + y1)
    # use local plane if x,y already meters — our trace x,y are UTM meters!
    dx = x1 - x0
    dy = y1 - y0
    dz = z1 - z0
    dist_h = math.hypot(dx, dy)
    n_h = int(dist_h / max_h_m) + 1 if dist_h > 0 else 1
    n_v = int(abs(dz) / max_v_m) + 1 if abs(dz) > 0 else 1
    n = max(n_h, n_v, 2)
    return [(i / n, x0 + (i / n) * dx, y0 + (i / n) * dy, z0 + (i / n) * dz) for i in range(n + 1)]


def refine_boundary(margin_fn, t_lo, t_hi, tol_s: float = 0.1, max_iter: int = 30):
    """Binary refine where sign changes. Returns refined (t_lo, t_hi)."""
    for _ in range(max_iter):
        if t_hi - t_lo <= tol_s:
            break
        t_mid = 0.5 * (t_lo + t_hi)
        m_lo = margin_fn(t_lo)
        m_hi = margin_fn(t_hi)
        m_mid = margin_fn(t_mid)
        if m_lo * m_mid <= 0:
            t_hi = t_mid
        elif m_mid * m_hi <= 0:
            t_lo = t_mid
        else:
            break
    return t_lo, t_hi


def compute_direct_margin_series(
    trace: pd.DataFrame,
    dem,
    g01: tuple[float, float, float],
    pareto_id: str,
    uav_xy_is_lonlat: bool = False,
) -> pd.DataFrame:
    """Sample each phase; return margin time series rows.

    Trace x,y are UTM meters (from our pipeline); DEM is lon/lat.
    Convert UTM->lon/lat for terrain LOS; use UTM xyz for distance? Spec says D is 3D
    Euclidean — use same coordinate frame as positions in the margin columns.

    We store x,y as UTM meters (trace) and convert to lon/lat only for DEM sampling.
    Distance uses 3D UTM+elev (consistent).
    """
    from pyproj import Transformer

    from src.common.schemas import EPSG_UTM49N, EPSG_WGS84
    from src.q3.link_budget import distance_m
    from src.q3.terrain_los import blocked_dense_sample, blocked_line_cells

    params, _ = load_comm_params()
    from src.q3.link_budget import build_link_budget_table

    l_max_tg = float(build_link_budget_table().set_index("pair").loc["transport<->G01", "L_max_db"])

    tf = Transformer.from_crs(EPSG_UTM49N, EPSG_WGS84, always_xy=True)
    glon, glat = tf.transform(g01[0], g01[1])
    g_ll_z = (glon, glat, g01[2])

    rows = []

    def margin_at(x, y, z, lonlat_cache={}):
        key = (round(x, 1), round(y, 1))
        if key not in lonlat_cache:
            lonlat_cache[key] = tf.transform(x, y)
        lon, lat = lonlat_cache[key]
        tpos = (lon, lat, z)
        d = distance_m((x, y, z), g01)  # UTM metric distance including z
        # terrain in lon/lat
        blocked = blocked_line_cells(dem, tpos[0], tpos[1], tpos[2], g_ll_z[0], g_ll_z[1], g_ll_z[2])
        from src.q3.link_budget import fspl_db, path_loss_db, margin_db

        l_fspl = fspl_db(params.f_mhz, d)
        l_path = path_loss_db(params, d, blocked)
        mc = margin_db(l_max_tg, l_path)
        mc_los = margin_db(l_max_tg, fspl_db(params.f_mhz, d))
        return mc, blocked, l_fspl, l_path, mc_los, d

    # walk phases
    for _, r in trace.iterrows():
        mc, blocked, l_fspl, l_path, mc_los, d = margin_at(float(r.x), float(r.y), float(r.z))
        rows.append(
            {
                "pareto_id": pareto_id,
                "sortie_id": r.task_id,
                "uav_id": r.node_id,
                "time": float(r.time),
                "phase": r["mode"],
                "phase_role": r.get("phase_role", ""),
                "x": float(r.x),
                "y": float(r.y),
                "z": float(r.z),
                "distance_to_G01": d,
                "los": 0 if blocked else 1,
                "L_fspl": l_fspl,
                "L_path": l_path,
                "L_max": l_max_tg,
                "M_C": mc,
                "M_C_LOS": mc_los,
                "direct_available": 1 if mc >= 0 else 0,
            }
        )
    return pd.DataFrame(rows)


def build_adaptive_series(trace: pd.DataFrame, dem, g01, pareto_id: str) -> pd.DataFrame:
    """Full adaptive sampling between phase endpoints + handover endpoints."""
    from src.q3.communication_margin import margin_pair
    from src.q3.link_budget import build_link_budget_table, load_comm_params

    params, _ = load_comm_params()
    l_max = float(build_link_budget_table().set_index("pair").loc["transport<->G01", "L_max_db"])
    from pyproj import Transformer
    from src.common.schemas import EPSG_UTM49N, EPSG_WGS84
    from src.q3.link_budget import distance_m, fspl_db, margin_db, path_loss_db
    from src.q3.terrain_los import blocked_line_cells

    tf = Transformer.from_crs(EPSG_UTM49N, EPSG_WGS84, always_xy=True)
    glon, glat = tf.transform(g01[0], g01[1])

    out = []
    tr = trace.sort_values("time", kind="mergesort").reset_index(drop=True)
    for i in range(len(tr) - 1):
        a, b = tr.iloc[i], tr.iloc[i + 1]
        mode = str(a["mode"])
        t0, t1 = float(a.time), float(b.time)
        x0, y0, z0 = float(a.x), float(a.y), float(a.z)
        x1, y1, z1 = float(b.x), float(b.y), float(b.z)
        samples = sample_flight_segment((x0, y0, z0, t0), (x1, y1, z1, t1))
        for frac, x, y, z in samples:
            t = t0 + frac * (t1 - t0)
            lon, lat = tf.transform(x, y)
            d = distance_m((x, y, z), (g01[0], g01[1], g01[2]))  # metric UTM
            from src.q3.terrain_los import blocked_line_cells

            blocked = blocked_line_cells(dem, lon, lat, z, glon, glat, g01[2])
            from src.q3.link_budget import fspl_db, path_loss_db, margin_db

            l_fspl = fspl_db(params.f_mhz, d)
            l_path = path_loss_db(params, d, blocked)
            mc = margin_db(l_max, l_path)
            mc_los = l_max - fspl_db(params.f_mhz, d)
            out.append(
                {
                    "pareto_id": pareto_id,
                    "sortie_id": a.task_id,
                    "uav_id": a.node_id,
                    "time": t,
                    "phase": mode,
                    "x": x,
                    "y": y,
                    "z": z,
                    "distance_to_G01": d,
                    "los": 0 if blocked else 1,
                    "L_fspl": l_fspl,
                    "L_path": l_path,
                    "L_max": l_max,
                    "M_C": mc,
                    "M_C_LOS": mc_los,
                    "direct_available": 1 if mc >= 0 else 0,
                }
            )
    df = pd.DataFrame(out).drop_duplicates(subset=["sortie_id", "time", "phase"], keep="first")
    return df.sort_values(["sortie_id", "time"]).reset_index(drop=True)


def extract_gaps(margin_df: pd.DataFrame) -> pd.DataFrame:
    cols = [
        "gap_id",
        "sortie_id",
        "uav_id",
        "start_s",
        "end_s",
        "duration_s",
        "phase_start",
        "phase_end",
        "min_margin_db",
        "cause",
    ]
    gaps = []
    gid = 0
    for sid, g in margin_df.groupby("sortie_id"):
        g = g.sort_values("time", kind="mergesort").reset_index(drop=True)
        in_gap = False
        t_start = None
        rows_in = []
        for _, r in g.iterrows():
            bad = r.M_C < 0
            if bad and not in_gap:
                in_gap = True
                t_start = float(r.time)
                rows_in = [r]
            elif bad and in_gap:
                rows_in.append(r)
            elif (not bad) and in_gap:
                in_gap = False
                t_end = float(r.time)
                # binary refine start between previous good and first bad
                # (samples are the margin series itself — keep discrete boundaries)
                seg = pd.DataFrame(rows_in)
                # shrink to core negative region
                neg = seg[seg.M_C < 0]
                if not neg.empty:
                    t_start = float(neg.time.min())
                    t_end = max(float(neg.time.max()), t_start)
                cause = classify_cause(neg if not neg.empty else seg)
                gaps.append(
                    {
                        "gap_id": gid,
                        "sortie_id": sid,
                        "uav_id": r.uav_id,
                        "start_s": t_start,
                        "end_s": t_end,
                        "duration_s": t_end - t_start,
                        "phase_start": rows_in[0]["phase"] if rows_in else "",
                        "phase_end": rows_in[-1]["phase"] if rows_in else "",
                        "min_margin_db": float(seg.M_C.min()) if len(seg) else None,
                        "cause": cause,
                    }
                )
                gid += 1
                rows_in = []
        if in_gap and rows_in:
            seg = pd.DataFrame(rows_in)
            neg = seg[seg.M_C < 0]
            t_end = float(g.time.max())
            if not neg.empty:
                t_start = float(neg.time.min())
                t_end = float(max(neg.time.max(), t_start))
            gaps.append(
                {
                    "gap_id": gid,
                    "sortie_id": sid,
                    "uav_id": g.uav_id.iloc[0],
                    "start_s": t_start,
                    "end_s": t_end,
                    "duration_s": t_end - t_start,
                    "phase_start": rows_in[0]["phase"],
                    "phase_end": rows_in[-1]["phase"],
                    "min_margin_db": float(seg.M_C.min()),
                    "cause": classify_cause(neg if not neg.empty else seg),
                }
            )
            gid += 1
    return pd.DataFrame(gaps, columns=cols)


def classify_cause(seg: pd.DataFrame) -> str:
    if seg.empty:
        return "UNKNOWN"
    los_neg = (seg.M_C_LOS < 0).any()
    block = (seg.M_C_LOS >= 0).any() and (seg.M_C < 0).any()
    # refine: if all samples in gap have M_C_LOS<0 -> distance
    if (seg.M_C_LOS < 0).all():
        return "DISTANCE_ONLY"
    if (seg.M_C_LOS >= 0).all():
        return "TERRAIN_BLOCKAGE"
    return "DISTANCE_AND_BLOCKAGE"
