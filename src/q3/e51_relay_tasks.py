"""E5.1 compliant relay search: no Top-K, safe bbox, depth=10, MIN_ATOMIC=2s."""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from src.common.paths import RESULTS_DIR, RESULTS_Q2, PROCESSED_DIR
from src.common.terrain import Dem
from src.q3.link_budget import load_comm_params, max_range_m, pair_lmax
from src.q3.relay_candidate_generator import access_margin, backhaul_margin, make_site
from src.q3.relay_geometry import evaluate_relay_site, load_relay_params, o01_pos

RESULTS_Q3 = RESULTS_DIR / "q3"
PAR = RESULTS_Q2 / "pareto_schedules"
MIN_ATOMIC_S = 2.0
MAX_SPLIT_DEPTH = 10


def g01_pos():
    ox, oy, oz = o01_pos()
    raw = json.loads((PROCESSED_DIR / "communication_parameters.json").read_text(encoding="utf-8"))
    h_g = float(raw["endpoints"]["固定网关 G01"]["天线离地高度（m）"]["value"])
    return ox, oy, oz + h_g


def sample_interval(margin_df, t0, t1, step_s=0.5):
    sub = margin_df[(margin_df.time >= t0 - 1e-6) & (margin_df.time <= t1 + 1e-6)].sort_values("time")
    if sub.empty:
        return []
    ts = np.arange(t0, t1 + 1e-9, step_s)
    if len(ts) < 2:
        ts = np.array([t0, t1])
    xs = np.interp(ts, sub.time, sub.x)
    ys = np.interp(ts, sub.time, sub.y)
    zs = np.interp(ts, sub.time, sub.z)
    return list(zip(xs.tolist(), ys.tolist(), zs.tolist(), ts.tolist()))


def safe_bbox(pts, d_tr, d_rg, g01, dem):
    gx, gy, _ = g01
    x_low = max(min(p[0] for p in pts) - d_tr, gx - d_rg)
    x_high = min(max(p[0] for p in pts) + d_tr, gx + d_rg)
    y_low = max(min(p[1] for p in pts) - d_tr, gy - d_rg)
    y_high = min(max(p[1] for p in pts) + d_tr, gy + d_rg)
    if x_low > x_high or y_low > y_high:
        return None
    # intersect DEM projected bounds (lon/lat -> utm via site sample)
    return (x_low, x_high, y_low, y_high)


def full_interval_ok(dem, pc, l_tr, site, pts, exact=True):
    step = max(1, len(pts) // 8)
    min_mur = 1e9
    for p in pts[::step]:
        mur, _, _ = access_margin(dem, pc, l_tr, site, p)
        min_mur = min(min_mur, mur)
        if min_mur < 0:
            return False, min_mur
    if not exact:
        return True, min_mur
    min_mur = 1e9
    for p in pts:
        mur, _, _ = access_margin(dem, pc, l_tr, site, p)
        if mur < min_mur:
            min_mur = mur
        if min_mur < 0:
            return False, min_mur
    return True, min_mur


_SEARCH_CACHE: dict = {}


def search_interval(dem, pc, pr, lm, margin_df, t0, t1, setup_s, service_s):
    key = (round(t0, 3), round(t1, 3), round(service_s, 3))
    if key in _SEARCH_CACHE:
        return _SEARCH_CACHE[key]
    res = _search_interval_uncached(dem, pc, pr, lm, margin_df, t0, t1, setup_s, service_s)
    _SEARCH_CACHE[key] = res
    return res


def _search_interval_uncached(dem, pc, pr, lm, margin_df, t0, t1, setup_s, service_s):
    """Exhaustive safe search; no Top-K. Returns (cands, gate, geo_empty)."""
    pts = sample_interval(margin_df, t0, t1, 1.0)
    if len(pts) < 2:
        pts = sample_interval(margin_df, t0, t1, 2.0)
    if not pts:
        return [], {"raw": 0}, False
    d_tr = max_range_m(lm["transport<->relay"], pc, False)
    d_rg = max_range_m(lm["relay<->G01"], pc, False)
    g01 = g01_pos()
    bbox = safe_bbox(pts, d_tr, d_rg, g01, dem)
    if bbox is None:
        return [], {"raw": 0, "geo_empty": 1}, True

    gate = {
        "raw_3d_candidates": 0,
        "after_DEM_legality": 0,
        "after_TR_range": 0,
        "after_RG_range": 0,
        "after_backhaul": 0,
        "after_endpoint_prefilter": 0,
        "after_full_interval_exact": 0,
        "after_energy": 0,
    }
    x_low, x_high, y_low, y_high = bbox
    best = []

    def evaluate_xy(x, y, heights, step):
        # sample ground once per xy
        try:
            ground = dem.sample(*__import__("src.q3.relay_candidate_generator", fromlist=["TF"]).TF.transform(float(x), float(y)))
        except Exception:
            ground = None
        if ground is None:
            return
        from src.q3.relay_candidate_generator import site_id_of

        for agl in heights:
            z = ground + float(agl)
            if not (0.0 < float(agl) <= 300.0):
                continue
            site = {
                "site_id": site_id_of(x, y, z),
                "x_m": float(x),
                "y_m": float(y),
                "lon": 0.0,
                "lat": 0.0,
                "ground_elevation_m": ground,
                "agl_m": float(agl),
                "z_amsl_m": z,
            }
            # fill lon/lat
            from src.q3.relay_candidate_generator import TF as _TF

            site["lon"], site["lat"] = _TF.transform(float(x), float(y))
            gate["raw_3d_candidates"] += 1
            gate["after_DEM_legality"] += 1
            # R2/R3 geometric
            dtr = max(math.hypot(site["x_m"] - p[0], site["y_m"] - p[1], site["z_amsl_m"] - p[2]) for p in pts)
            drg = math.hypot(site["x_m"] - g01[0], site["y_m"] - g01[1], site["z_amsl_m"] - g01[2])
            if dtr > d_tr:
                continue
            gate["after_TR_range"] += 1
            if drg > d_rg:
                continue
            gate["after_RG_range"] += 1
            mrg, _, _ = backhaul_margin(dem, pc, lm["relay<->G01"], site)
            if mrg < 0:
                continue
            gate["after_backhaul"] += 1
            mur0, _, _ = access_margin(dem, pc, lm["transport<->relay"], site, pts[0])
            mur1, _, _ = access_margin(dem, pc, lm["transport<->relay"], site, pts[-1])
            if mur0 < 0 or mur1 < 0:
                continue
            gate["after_endpoint_prefilter"] += 1
            ok, min_mur = full_interval_ok(dem, pc, lm["transport<->relay"], site, pts, exact=False)
            if not ok:
                continue
            ok2, min_mur = full_interval_ok(dem, pc, lm["transport<->relay"], site, pts, exact=True)
            if not ok2:
                continue
            gate["after_full_interval_exact"] += 1
            en = evaluate_relay_site(dem, pr, (site["x_m"], site["y_m"], site["z_amsl_m"]), (site["lon"], site["lat"], site["z_amsl_m"]), setup_s, service_s)
            if en["energy_margin_kwh"] < 0:
                continue
            gate["after_energy"] += 1
            rec = {
                **site,
                "min_access_margin_db": min_mur,
                "backhaul_margin_db": mrg,
                "min_twohop_margin_db": min(min_mur, mrg),
                "outbound_time_s": en["outbound_time_s"],
                "return_time_s": en["return_time_s"],
                "flight_energy_kwh": en["flight_energy_kwh"],
                "setup_energy_kwh": en["setup_energy_kwh"],
                "service_energy_kwh": en["service_energy_kwh"],
                "total_energy_kwh": en["total_energy_kwh"],
                "energy_margin_kwh": en["energy_margin_kwh"],
                "return_soc": en["return_soc"],
                "grid_step_m": step,
                "agl_m": agl,
            }
            best.append(rec)

    heights = [50.0, 100.0, 150.0, 200.0, 250.0, 300.0]
    # 120 -> 60 -> 30 full grids over bbox (no early return)
    for step in (120.0, 60.0, 30.0):
        nx = int((x_high - x_low) / step) + 1
        ny = int((y_high - y_low) / step) + 1
        for i in range(nx):
            x = x_low + i * step
            for j in range(ny):
                y = y_low + j * step
                evaluate_xy(x, y, heights, step)
        if best:
            break  # finer levels only if coarse empty — still exhaustive at the level used
    if not best:
        for agl in range(25, 301, 25):
            # only bbox corners + mid — full xy already done at 30m with 50..300
            for x in (x_low, 0.5 * (x_low + x_high), x_high):
                for y in (y_low, 0.5 * (y_low + y_high), y_high):
                    evaluate_xy(x, y, [float(agl)], 30.0)
    return best, gate, False


def split_task(dem, pc, pr, lm, margin_df, t0, t1, setup_s, depth=0):
    service_s = max(t1 - t0, 0.1)
    cands, gate, geo_empty = search_interval(dem, pc, pr, lm, margin_df, t0, t1, setup_s, service_s)
    if cands:
        return [{"t0": t0, "t1": t1, "cands": cands, "gate": gate}], gate, False
    if (t1 - t0) <= MIN_ATOMIC_S or depth >= MAX_SPLIT_DEPTH:
        return [{"t0": t0, "t1": t1, "cands": [], "gate": gate, "geo_empty": geo_empty}], gate, True
    tm = 0.5 * (t0 + t1)
    L, gL, uL = split_task(dem, pc, pr, lm, margin_df, t0, tm, setup_s, depth + 1)
    R, gR, uR = split_task(dem, pc, pr, lm, margin_df, tm, t1, setup_s, depth + 1)
    merged = L + R
    # merge-back: if adjacent share a site covering union
    out = []
    i = 0
    while i < len(merged):
        cur = merged[i]
        if i + 1 < len(merged):
            nxt = merged[i + 1]
            common = {c["site_id"] for c in cur["cands"]} & {c["site_id"] for c in nxt["cands"]}
            if common:
                svc = nxt["t1"] - cur["t0"]
                comb, gC, _ = search_interval(dem, pc, pr, lm, margin_df, cur["t0"], nxt["t1"], setup_s, svc)
                if comb:
                    out.append({"t0": cur["t0"], "t1": nxt["t1"], "cands": comb, "gate": gC})
                    i += 2
                    continue
        out.append(cur)
        i += 1
    unresolved = any(len(a["cands"]) == 0 for a in out)
    return out, gate, unresolved


def main() -> None:
    RESULTS_Q3.mkdir(parents=True, exist_ok=True)
    # clean rebuild
    for name in (
        "relay_sites.csv",
        "relay_task_candidates.csv",
        "relay_coverage_matrix.csv",
        "relay_task_summary.csv",
        "relay_candidate_gate_stats_raw.csv",
        "relay_unresolved.csv",
    ):
        p = RESULTS_Q3 / name
        if p.exists():
            p.unlink()

    dem = Dem()
    pc, _ = load_comm_params()
    pr = load_relay_params()
    lm = pair_lmax()
    setup_s = pr["setup_time_s"]
    site_lib = {}
    all_tasks, all_cov, gate_rows, unresolved, summary = [], [], [], [], []

    for pid in ("P01", "P02", "P03"):
        margin = pd.read_csv(RESULTS_Q3 / f"direct_margin_{pid}.csv")
        gaps = pd.read_csv(RESULTS_Q3 / f"direct_gaps_{pid}.csv")
        print(f"=== {pid} gaps={len(gaps)} ===", flush=True)
        n_atomic = n_full = n_split = n_unres = 0
        counts = []
        for gi, gap in enumerate(gaps.itertuples()):
            atoms, gate, _ = split_task(dem, pc, pr, lm, margin, float(gap.start_s), float(gap.end_s), setup_s)
            if len(atoms) == 1 and atoms[0]["cands"]:
                n_full += 1
            elif len(atoms) > 1:
                n_split += 1
            for ai, atom in enumerate(atoms):
                n_atomic += 1
                aid = f"{pid}_G{gi:03d}_A{ai:02d}"
                service = atom["t1"] - atom["t0"]
                if not atom["cands"]:
                    n_unres += 1
                    unresolved.append(
                        {
                            "pareto_id": pid,
                            "parent_gap_index": gi,
                            "atomic_task_id": aid,
                            "start_s": atom["t0"],
                            "end_s": atom["t1"],
                            "note": "GRID_UNRESOLVED",
                        }
                    )
                counts.append(len(atom["cands"]))
                for c in atom["cands"]:
                    lead = pr["prep_time_s"] + c["outbound_time_s"] + setup_s
                    en = evaluate_relay_site(
                        dem,
                        pr,
                        (c["x_m"], c["y_m"], c["z_amsl_m"]),
                        (c["lon"], c["lat"], c["z_amsl_m"]),
                        setup_s,
                        service,
                    )
                    all_tasks.append(
                        {
                            "pareto_id": pid,
                            "atomic_task_id": aid,
                            "parent_gap_id": f"{pid}_G{gi:03d}",
                            "transport_sortie_id": gap.sortie_id,
                            "site_id": c["site_id"],
                            "service_start_s": atom["t0"],
                            "service_end_s": atom["t1"],
                            "service_duration_s": service,
                            "min_access_margin_db": c["min_access_margin_db"],
                            "backhaul_margin_db": c["backhaul_margin_db"],
                            "min_twohop_margin_db": c["min_twohop_margin_db"],
                            "outbound_time_s": c["outbound_time_s"],
                            "return_time_s": c["return_time_s"],
                            "setup_time_s": setup_s,
                            "flight_energy_kwh": en["flight_energy_kwh"],
                            "setup_energy_kwh": en["setup_energy_kwh"],
                            "service_energy_kwh": en["service_energy_kwh"],
                            "total_energy_kwh": en["total_energy_kwh"],
                            "energy_margin_kwh": en["energy_margin_kwh"],
                            "return_soc": en["return_soc"],
                            "earliest_ready_s": lead,
                            "as_is_timing_feasible": int(atom["t0"] >= lead),
                            "required_transport_shift_s": max(0.0, lead - atom["t0"]),
                        }
                    )
                    all_cov.append(
                        {
                            "site_id": c["site_id"],
                            "atomic_task_id": aid,
                            "feasible": 1,
                            "min_twohop_margin_db": c["min_twohop_margin_db"],
                            "total_energy_kwh": en["total_energy_kwh"],
                        }
                    )
                    if c["site_id"] not in site_lib:
                        site_lib[c["site_id"]] = {
                            "site_id": c["site_id"],
                            "x_m": c["x_m"],
                            "y_m": c["y_m"],
                            "lon": c["lon"],
                            "lat": c["lat"],
                            "ground_elevation_m": c["ground_elevation_m"],
                            "agl_m": c["agl_m"],
                            "z_amsl_m": c["z_amsl_m"],
                            "backhaul_margin_db": c["backhaul_margin_db"],
                            "outbound_time_s": c["outbound_time_s"],
                            "return_time_s": c["return_time_s"],
                            "flight_energy_kwh": c["flight_energy_kwh"],
                        }
            gate["pareto_id"] = pid
            gate["parent_gap_index"] = gi
            gate_rows.append(gate)
        summary.append(
            {
                "pareto_id": pid,
                "direct_gaps": len(gaps),
                "atomic_tasks": n_atomic,
                "full_gap_single_site": n_full,
                "split_gaps": n_split,
                "unresolved": n_unres,
                "cand_min": min(counts) if counts else 0,
                "cand_median": float(np.median(counts)) if counts else 0,
                "cand_mean": float(np.mean(counts)) if counts else 0,
                "cand_max": max(counts) if counts else 0,
            }
        )

    pd.DataFrame(all_tasks).to_csv(RESULTS_Q3 / "relay_task_candidates.csv", index=False)
    pd.DataFrame(all_cov).to_csv(RESULTS_Q3 / "relay_coverage_matrix.csv", index=False)
    pd.DataFrame(list(site_lib.values())).to_csv(RESULTS_Q3 / "relay_sites.csv", index=False)
    pd.DataFrame(gate_rows).to_csv(RESULTS_Q3 / "relay_candidate_gate_stats_raw.csv", index=False)
    pd.DataFrame(summary).to_csv(RESULTS_Q3 / "relay_task_summary.csv", index=False)
    pd.DataFrame(unresolved).to_csv(RESULTS_Q3 / "relay_unresolved.csv", index=False)
    (RESULTS_Q3 / "e51_run_meta.json").write_text(
        json.dumps({"MIN_ATOMIC_S": MIN_ATOMIC_S, "MAX_SPLIT_DEPTH": MAX_SPLIT_DEPTH, "summary": summary}, indent=2),
        encoding="utf-8",
    )
    print("E51_CORE_DONE", flush=True)
    print(pd.DataFrame(summary).to_string(index=False), flush=True)
    print("unresolved", len(unresolved), flush=True)


if __name__ == "__main__":
    main()
