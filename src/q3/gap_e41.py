"""E4.1: per-sortie continuous direct-margin + gaps (no cross-sortie interpolation)."""
from __future__ import annotations

import math

import pandas as pd
from pyproj import Transformer

from src.common.schemas import EPSG_UTM49N, EPSG_WGS84
from src.q3.link_budget import distance_m, fspl_db, load_comm_params, margin_db, path_loss_db, pair_lmax
from src.q3.terrain_los import blocked_line_cells

TF = Transformer.from_crs(EPSG_UTM49N, EPSG_WGS84, always_xy=True)
BOUNDARY_TOL_S = 0.1


def _ll(x, y):
    return TF.transform(x, y)


def margin_at(dem, params, l_max, g01, g_ll, x, y, z):
    lon, lat = _ll(x, y)
    d = distance_m((x, y, z), (g01[0], g01[1], g01[2]))
    blocked = blocked_line_cells(dem, lon, lat, z, g_ll[0], g_ll[1], g_ll[2])
    l_fspl = fspl_db(params.f_mhz, d)
    l_path = path_loss_db(params, d, blocked)
    mc = margin_db(l_max, l_path)
    mc_los = l_max - l_fspl
    return mc, blocked, l_fspl, l_path, mc_los, d


def lerp(a, b, t):
    return a + (b - a) * t


def sample_segment(t0, x0, y0, z0, t1, x1, y1, z1, max_h=15.0, max_v=5.0):
    dh = math.hypot(x1 - x0, y1 - y0)
    dv = abs(z1 - z0)
    n = max(int(dh / max_h) + 1 if dh > 0 else 1, int(dv / max_v) + 1 if dv > 0 else 1, 2)
    out = []
    for i in range(n + 1):
        u = i / n
        out.append((lerp(t0, t1, u), lerp(x0, x1, u), lerp(y0, y1, u), lerp(z0, z1, u)))
    return out


def refine_boundary(fn_mc, fn_los, t_lo, t_hi, tol=BOUNDARY_TOL_S, max_iter=40):
    """Binary refine sign(M_C) or LOS change. Returns (t_lo, t_hi)."""
    m_lo = fn_mc(t_lo)
    m_hi = fn_mc(t_hi)
    l_lo = fn_los(t_lo)
    l_hi = fn_los(t_hi)
    changed = (m_lo * m_hi < 0) or (l_lo != l_hi) or (m_lo < 0) != (m_hi < 0)
    if not changed and (m_lo < 0) == (m_hi < 0):
        return t_lo, t_hi
    for _ in range(max_iter):
        if t_hi - t_lo <= tol:
            break
        t_mid = 0.5 * (t_lo + t_hi)
        m_mid = fn_mc(t_mid)
        l_mid = fn_los(t_mid)
        if (m_lo * m_mid <= 0) or (l_lo != l_mid) or ((m_lo < 0) != (m_mid < 0)):
            t_hi, m_hi, l_hi = t_mid, m_mid, l_mid
        else:
            t_lo, m_lo, l_lo = t_mid, m_mid, l_mid
    return t_lo, t_hi


def analyze_sortie(trace_s: pd.DataFrame, dem, g01, g_ll, params, l_max, pareto_id: str) -> tuple[pd.DataFrame, list[dict]]:
    """Analyze one sortie only (takeoff..return). Returns margin df + gap dicts."""
    trace_s = trace_s.sort_values("time", kind="mergesort").reset_index(drop=True)
    # drop prep: keep takeoff and later (or first point at takeoff)
    takeoff = float(trace_s.loc[trace_s["mode"] == "takeoff", "time"].min()) if (trace_s["mode"] == "takeoff").any() else float(trace_s.time.min())
    ret = float(trace_s.loc[trace_s["mode"] == "return", "time"].max()) if (trace_s["mode"] == "return").any() else float(trace_s.time.max())
    sid = str(trace_s.task_id.iloc[0])
    uid = str(trace_s.node_id.iloc[0])

    def pos_at(t, a, b):
        u = 0.0 if abs(b.time - a.time) < 1e-12 else (t - float(a.time)) / (float(b.time) - float(a.time))
        return lerp(float(a.x), float(b.x), u), lerp(float(a.y), float(b.y), u), lerp(float(a.z), float(b.z), u)

    samples = []  # (t,x,y,z,phase)
    for i in range(len(trace_s) - 1):
        a, b = trace_s.iloc[i], trace_s.iloc[i + 1]
        t0, t1 = float(a.time), float(b.time)
        if t1 < takeoff - 1e-6 or t0 > ret + 1e-6:
            continue
        mode = str(a["mode"])
        # clip to [takeoff, ret]
        if t1 <= t0 + 1e-12:
            t1c = min(max(t1, takeoff), ret)
            x, y, z = float(b.x), float(b.y), float(b.z)
            if t1c >= takeoff - 1e-9:
                samples.append((t1c, x, y, z, mode))
            continue
        for t, x, y, z in sample_segment(t0, float(a.x), float(a.y), float(a.z), t1, float(b.x), float(b.y), float(b.z)):
            if t < takeoff - 1e-6 or t > ret + 1e-6:
                continue
            samples.append((t, x, y, z, mode))
    # unique
    uniq = {}
    for t, x, y, z, mode in samples:
        uniq[round(t, 6)] = (t, x, y, z, mode)
    samples = [uniq[k] for k in sorted(uniq)]

    rows = []
    for t, x, y, z, mode in samples:
        mc, blocked, lfs, lpath, mc_los, d = margin_at(dem, params, l_max, g01, g_ll, x, y, z)
        rows.append(
            {
                "pareto_id": pareto_id,
                "sortie_id": sid,
                "uav_id": uid,
                "time": t,
                "phase": mode,
                "x": x,
                "y": y,
                "z": z,
                "distance_to_G01": d,
                "los": 0 if blocked else 1,
                "L_fspl": lfs,
                "L_path": lpath,
                "L_max": l_max,
                "M_C": mc,
                "M_C_LOS": mc_los,
                "direct_available": 1 if mc >= 0 else 0,
            }
        )
    mdf = pd.DataFrame(rows).sort_values("time", kind="mergesort").reset_index(drop=True)

    # binary refine where sign(M_C) or los changes
    refined_rows = []
    gaps = []
    in_gap = False
    gap_start = None
    gap_rows = []
    for i in range(len(mdf) - 1):
        a, b = mdf.iloc[i], mdf.iloc[i + 1]
        refined_rows.append(a.to_dict())
        s_a, s_b = (a.M_C < 0), (b.M_C < 0)
        los_change = int(a.los) != int(b.los)

        def mc_fn(t, a=a, b=b):
            x, y, z = pos_at(t, a, b)
            return margin_at(dem, params, l_max, g01, g_ll, x, y, z)[0]

        def los_fn(t, a=a, b=b):
            x, y, z = pos_at(t, a, b)
            return margin_at(dem, params, l_max, g01, g_ll, x, y, z)[1]

        if (s_a != s_b) or los_change:
            t_lo, t_hi = refine_boundary(mc_fn, los_fn, float(a.time), float(b.time))
            x, y, z = pos_at(t_hi, a, b)
            mc, blocked, lfs, lpath, mc_los, d = margin_at(dem, params, l_max, g01, g_ll, x, y, z)
            refined_rows.append(
                {
                    "pareto_id": pareto_id,
                    "sortie_id": sid,
                    "uav_id": uid,
                    "time": t_hi,
                    "phase": str(a["phase"]),
                    "x": x,
                    "y": y,
                    "z": z,
                    "distance_to_G01": d,
                    "los": 0 if blocked else 1,
                    "L_fspl": lfs,
                    "L_path": lpath,
                    "L_max": l_max,
                    "M_C": mc,
                    "M_C_LOS": mc_los,
                    "direct_available": 1 if mc >= 0 else 0,
                }
            )
            b_new = refined_rows[-1]
            s_b = b_new["M_C"] < 0
        else:
            b_new = b.to_dict()

        if s_a and not in_gap:
            in_gap = True
            gap_start = float(a.time)
            gap_rows = [a]
        elif s_a and in_gap:
            gap_rows.append(a)
        elif (not s_a) and in_gap:
            in_gap = False
            t_end = float(refined_rows[-1]["time"])
            seg = pd.DataFrame(gap_rows)
            dur = t_end - gap_start
            if dur > BOUNDARY_TOL_S:
                cause = classify(seg)
                gaps.append(
                    {
                        "pareto_id": pareto_id,
                        "sortie_id": sid,
                        "uav_id": uid,
                        "start_s": gap_start,
                        "end_s": t_end,
                        "duration_s": dur,
                        "phase_start": str(gap_rows[0]["phase"]),
                        "phase_end": str(gap_rows[-1]["phase"]),
                        "min_margin_db": float(seg.M_C.min()),
                        "cause": cause,
                    }
                )
            gap_rows = []
    refined_rows.append(mdf.iloc[-1].to_dict())
    if in_gap and gap_rows:
        t_end = ret
        seg = pd.DataFrame(gap_rows)
        dur = t_end - gap_start
        if dur > BOUNDARY_TOL_S:
            gaps.append(
                {
                    "pareto_id": pareto_id,
                    "sortie_id": sid,
                    "uav_id": uid,
                    "start_s": gap_start,
                    "end_s": t_end,
                    "duration_s": dur,
                    "phase_start": str(gap_rows[0]["phase"]),
                    "phase_end": str(gap_rows[-1]["phase"]),
                    "min_margin_db": float(seg.M_C.min()),
                    "cause": classify(seg),
                }
            )
    out = pd.DataFrame(refined_rows).sort_values("time", kind="mergesort").drop_duplicates(
        subset=["sortie_id", "time"], keep="last"
    ).reset_index(drop=True)
    return out, gaps


def classify(seg: pd.DataFrame) -> str:
    if seg.empty:
        return "UNKNOWN"
    if (seg.M_C_LOS < 0).all():
        return "DISTANCE_ONLY"
    if (seg.M_C_LOS >= 0).all():
        return "TERRAIN_BLOCKAGE"
    return "DISTANCE_AND_BLOCKAGE"


def analyze_pareto_plan(pid: str, trace: pd.DataFrame, dem, g01, g_ll, params, l_max) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    margins = []
    gaps = []
    for sid, g in trace.groupby("task_id"):
        m, gs = analyze_sortie(g, dem, g01, g_ll, params, l_max, pid)
        margins.append(m)
        gaps.extend(gs)
        # activity assertions
        t0 = float(m.time.min())
        t1 = float(m.time.max())
        # find takeoff/return from original
        gg = g.sort_values("time")
        to = float(gg.loc[gg["mode"] == "takeoff", "time"].min())
        re = float(gg.loc[gg["mode"] == "return", "time"].max())
        assert abs(t0 - to) <= 0.15 or t0 >= to - 1e-6
        assert abs(t1 - re) <= 0.15 or t1 <= re + 1e-6
    mdf = pd.concat(margins, ignore_index=True) if margins else pd.DataFrame()
    gdf = pd.DataFrame(gaps)
    if gdf.empty:
        gdf = pd.DataFrame(
            columns=[
                "pareto_id",
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
        )
    # burden identity
    active = gap_time = avail = 0.0
    for sid, g in mdf.groupby("sortie_id"):
        g = g.sort_values("time")
        a0, a1 = float(g.time.min()), float(g.time.max())
        active += a1 - a0
        for i in range(len(g) - 1):
            dt = float(g.time.iloc[i + 1] - g.time.iloc[i])
            if g.direct_available.iloc[i] >= 1:
                avail += dt
            else:
                gap_time += dt
    burden = {
        "pareto_id": pid,
        "active_time_s": active,
        "direct_available_time_s": avail,
        "direct_gap_time_s": gap_time,
        "direct_available_ratio": (avail / active) if active > 0 else None,
        "gap_count": int(len(gdf)),
        "max_gap_s": float(gdf.duration_s.max()) if len(gdf) else 0.0,
        "sorties_requiring_relay": int(gdf.sortie_id.nunique()) if len(gdf) else 0,
        "min_margin_db": float(mdf.M_C.min()) if len(mdf) else None,
        "terrain_gap_s": float(gdf.loc[gdf.cause.isin(["TERRAIN_BLOCKAGE", "DISTANCE_AND_BLOCKAGE"]), "duration_s"].sum()) if len(gdf) else 0.0,
        "distance_gap_s": float(gdf.loc[gdf.cause.isin(["DISTANCE_ONLY", "DISTANCE_AND_BLOCKAGE"]), "duration_s"].sum()) if len(gdf) else 0.0,
    }
    return mdf, gdf, burden
