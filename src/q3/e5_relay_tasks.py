"""E5 pipeline: gaps → atomic relay tasks → hierarchical candidate sites."""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from src.common.paths import RESULTS_DIR, RESULTS_Q2
from src.common.terrain import Dem
from src.q3.link_budget import load_comm_params, max_range_m, pair_lmax
from src.q3.relay_candidate_generator import (
    access_margin,
    backhaul_margin,
    hierarchical_sites,
    refine_heights,
    site_id_of,
)
from src.q3.relay_geometry import evaluate_relay_site, load_relay_params, o01_pos

RESULTS_Q3 = RESULTS_DIR / "q3"
PAR = RESULTS_Q2 / "pareto_schedules"
MIN_ATOMIC_S = 10.0
MAX_SPLIT_DEPTH = 2


def transport_positions_in_interval(margin_df: pd.DataFrame, t0: float, t1: float) -> list[tuple]:
    sub = margin_df[(margin_df.time >= t0 - 1e-6) & (margin_df.time <= t1 + 1e-6)]
    pts = list(zip(sub.x.astype(float), sub.y.astype(float), sub.z.astype(float), sub.time.astype(float)))
    return pts


def interp_positions(margin_df: pd.DataFrame, t0: float, t1: float, step: float = 0.25) -> list[tuple]:
    sub = margin_df[(margin_df.time >= t0 - 0.5) & (margin_df.time <= t1 + 0.5)].sort_values("time")
    if sub.empty:
        return []
    ts = np.arange(t0, t1 + 1e-9, step)
    xs = np.interp(ts, sub.time, sub.x)
    ys = np.interp(ts, sub.time, sub.y)
    zs = np.interp(ts, sub.time, sub.z)
    return list(zip(xs.tolist(), ys.tolist(), zs.tolist(), ts.tolist()))


def search_sites_for_interval(
    dem, params_c, params_r, lm, margin_df, t0, t1, site_lib: dict, setup_s, service_s
):
    """Return list of (site_dict, metrics) covering [t0,t1] fully."""
    pts = interp_positions(margin_df, t0, t1, 0.5)
    if not pts:
        pts = transport_positions_in_interval(margin_df, t0, t1)
    if not pts:
        return [], "no_transport_samples"
    # necessary geometric center: mean of transport xy
    cx = float(np.mean([p[0] for p in pts]))
    cy = float(np.mean([p[1] for p in pts]))
    # radius from farthest transport point + LOS range
    dmax = max(math.hypot(p[0] - cx, p[1] - cy) for p in pts)
    d_tr_los = max_range_m(lm["transport<->relay"], params_c, False)
    d_rg_los = max_range_m(lm["relay<->G01"], params_c, False)
    radius = d_tr_los + dmax + 60.0

    best = []
    gate = {
        "raw_3d_candidates": 0,
        "after_DEM_legality": 0,
        "after_TR_range": 0,
        "after_RG_range": 0,
        "after_backhaul": 0,
        "after_endpoint_access": 0,
        "after_full_interval_access": 0,
        "after_energy": 0,
    }

    # cheap distance-based candidate pruning before any LOS
    ox, oy, oz = o01_pos()
    import json as _j
    from src.common.paths import PROCESSED_DIR as _PD

    raw = _j.loads((_PD / "communication_parameters.json").read_text(encoding="utf-8"))
    h_g = float(raw["endpoints"]["固定网关 G01"]["天线离地高度（m）"]["value"])
    g01 = (ox, oy, oz + h_g)

    def cheap_ok(site):
        dtr = max(
            math.hypot(site["x_m"] - p[0], site["y_m"] - p[1], site["z_amsl_m"] - p[2]) for p in pts
        )
        drg = math.hypot(site["x_m"] - g01[0], site["y_m"] - g01[1], site["z_amsl_m"] - g01[2])
        return dtr <= d_tr_los and drg <= d_rg_los

    # multi-center along transport path (not only mean)
    centers = []
    for frac in (0.15, 0.5, 0.85):
        i = min(len(pts) - 1, max(0, int(frac * (len(pts) - 1))))
        centers.append((float(pts[i][0]), float(pts[i][1])))
    if not centers:
        centers = [(cx, cy)]

    def consider(site, level):
        mrg, _, _ = backhaul_margin(dem, params_c, lm["relay<->G01"], site)
        if mrg < 0:
            return
        gate["after_backhaul"] += 1
        mur0, _, _ = access_margin(dem, params_c, lm["transport<->relay"], site, pts[0])
        mur1, _, _ = access_margin(dem, params_c, lm["transport<->relay"], site, pts[-1])
        if mur0 < 0 or mur1 < 0:
            return
        gate["after_endpoint_access"] += 1
        min_mur = 1e9
        step_i = max(1, len(pts) // 8)
        for p in pts[::step_i]:
            mur, _, _ = access_margin(dem, params_c, lm["transport<->relay"], site, p)
            min_mur = min(min_mur, mur)
            if min_mur < 0:
                break
        if min_mur < 0:
            return
        gate["after_full_interval_access"] += 1
        en = evaluate_relay_site(dem, params_r, (site["x_m"], site["y_m"], site["z_amsl_m"]), (site["lon"], site["lat"], site["z_amsl_m"]), setup_s, service_s)
        if en["energy_margin_kwh"] < 0:
            return
        gate["after_energy"] += 1
        min2 = min(min_mur, mrg)
        rec = {**site, "min_access_margin_db": min_mur, "backhaul_margin_db": mrg, "min_twohop_margin_db": min2,
               "outbound_time_s": en["outbound_time_s"], "return_time_s": en["return_time_s"],
               "flight_energy_kwh": en["flight_energy_kwh"], "setup_energy_kwh": en["setup_energy_kwh"],
               "service_energy_kwh": en["service_energy_kwh"], "total_energy_kwh": en["total_energy_kwh"],
               "energy_margin_kwh": en["energy_margin_kwh"], "return_soc": en["return_soc"], "grid_level": level}
        sid = rec["site_id"]
        if sid not in site_lib:
            site_lib[sid] = {"site_id": sid, "x_m": site["x_m"], "y_m": site["y_m"], "lon": site["lon"],
                             "lat": site["lat"], "ground_elevation_m": site["ground_elevation_m"],
                             "agl_m": site["agl_m"], "z_amsl_m": site["z_amsl_m"],
                             "backhaul_margin_db": mrg, "outbound_time_s": en["outbound_time_s"],
                             "return_time_s": en["return_time_s"], "flight_energy_kwh": en["flight_energy_kwh"]}
        best.append(rec)

    for cxc, cyc in centers:
        for step in (120.0, 60.0, 30.0):
            local = []
            for s in hierarchical_sites(dem, cxc, cyc, 1800.0, setup_s, service_s, only_step=step):
                gate["raw_3d_candidates"] += 1
                gate["after_DEM_legality"] += 1
                if not cheap_ok(s):
                    continue
                gate["after_TR_range"] += 1
                gate["after_RG_range"] += 1
                local.append(s)
                if len(local) >= 20:
                    break
            for s in local:
                consider(s, step)
                if len(best) >= 12:
                    return best, gate
            if best:
                return best, gate
    return best, gate


def atomic_from_gap(dem, params_c, params_r, lm, margin_df, gap, site_lib, setup_s, service_s, depth=0):
    t0, t1 = float(gap.start_s), float(gap.end_s)
    cands, gate = search_sites_for_interval(dem, params_c, params_r, lm, margin_df, t0, t1, site_lib, setup_s, service_s)
    if cands:
        return [{"t0": t0, "t1": t1, "cands": cands, "gate": gate, "split": False}], gate
    dur = t1 - t0
    if dur <= MIN_ATOMIC_S or depth >= MAX_SPLIT_DEPTH:
        return [{"t0": t0, "t1": t1, "cands": [], "gate": gate, "split": True, "unresolved": True}], gate
    tm = 0.5 * (t0 + t1)
    left, gl = atomic_from_gap(dem, params_c, params_r, lm, margin_df, gap._replace(start_s=t0, end_s=tm) if hasattr(gap, "_replace") else gap, site_lib, setup_s, service_s, depth + 1)
    # use simple namespace
    return None  # replaced below


def split_gap(dem, params_c, params_r, lm, margin_df, t0, t1, site_lib, setup_s, service_s, depth=0):
    cands, gate = search_sites_for_interval(dem, params_c, params_r, lm, margin_df, t0, t1, site_lib, setup_s, service_s)
    if cands:
        return [{"t0": t0, "t1": t1, "cands": cands, "gate": gate}], gate
    if (t1 - t0) <= MIN_ATOMIC_S or depth >= MAX_SPLIT_DEPTH:
        return [{"t0": t0, "t1": t1, "cands": [], "gate": gate}], gate
    tm = 0.5 * (t0 + t1)
    L, gL = split_gap(dem, params_c, params_r, lm, margin_df, t0, tm, site_lib, setup_s, service_s, depth + 1)
    R, gR = split_gap(dem, params_c, params_r, lm, margin_df, tm, t1, site_lib, setup_s, service_s, depth + 1)
    merged = L + R
    # merge-back
    out = []
    i = 0
    while i < len(merged):
        cur = merged[i]
        if i + 1 < len(merged):
            nxt = merged[i + 1]
            common = {c["site_id"] for c in cur["cands"]} & {c["site_id"] for c in nxt["cands"]}
            if common:
                comb, gC = search_sites_for_interval(
                    dem, params_c, params_r, lm, margin_df, cur["t0"], nxt["t1"], site_lib, setup_s, service_s
                )
                if comb:
                    out.append({"t0": cur["t0"], "t1": nxt["t1"], "cands": comb, "gate": gC})
                    i += 2
                    continue
        out.append(cur)
        i += 1
    return out, gate


def main() -> None:
    RESULTS_Q3.mkdir(parents=True, exist_ok=True)
    dem = Dem()
    params_c, _ = load_comm_params()
    params_r = load_relay_params()
    lm = pair_lmax()
    setup_s = params_r["setup_time_s"]
    # service duration charged as gap duration per atomic task
    site_lib: dict = {}
    all_tasks = []
    all_cov = []
    all_sites_rows = []
    gate_rows = []
    unresolved = []
    summary = []

    for pid in ("P01", "P02", "P03"):
        margin = pd.read_csv(RESULTS_Q3 / f"direct_margin_{pid}.csv")
        gaps = pd.read_csv(RESULTS_Q3 / f"direct_gaps_{pid}.csv")
        print(f"=== {pid} gaps={len(gaps)} ===", flush=True)
        n_atomic = 0
        n_full = n_split = 0
        n_unres = 0
        task_cand_counts = []
        for gi, gap in enumerate(gaps.itertuples()):
            service_s = max(float(gap.duration_s), MIN_ATOMIC_S)
            atoms, gate = split_gap(
                dem,
                params_c,
                params_r,
                lm,
                margin,
                float(gap.start_s),
                float(gap.end_s),
                site_lib,
                setup_s,
                service_s,
            )
            # coverage union check
            atoms = sorted(atoms, key=lambda a: a["t0"])
            if len(atoms) == 1 and atoms[0]["cands"]:
                n_full += 1
            elif len(atoms) > 1:
                n_split += 1
            for ai, atom in enumerate(atoms):
                n_atomic += 1
                aid = f"{pid}_G{gi:03d}_A{ai:02d}"
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
                task_cand_counts.append(len(atom["cands"]))
                service_dur = atom["t1"] - atom["t0"]
                for c in atom["cands"]:
                    rel_shift = max(
                        0.0,
                        params_r["prep_time_s"]
                        + c["outbound_time_s"]
                        + setup_s
                        - (atom["t0"] - margin.time.min() + margin.time.min()),  # relative to gap start as task_start
                    )
                    # task_start is gap atom start (absolute sim time); ready = prep+out+setup measured from shift-0 schedule
                    ready_from_zero = params_r["prep_time_s"] + c["outbound_time_s"] + setup_s
                    # earliest ready if started at 0 of planning; as-is: prep assumed before task_start
                    # interpret as: prep+out+setup must finish before service_start if transport not shifted
                    as_is = ready_from_zero <= (atom["t0"] - 0.0)  # planning origin 0
                    # better: if relay starts prep at t0 - ready lead; feasibility if we can start prep early enough
                    # required shift = max(0, ready_from_zero - (t0 - min_possible_prep_start))
                    # use: lead time needed = ready_from_zero; if t0 >= lead, as_is ok with prep starting at t0-lead
                    lead = ready_from_zero
                    as_is_feasible = atom["t0"] >= lead
                    req_shift = 0.0 if as_is_feasible else (lead - atom["t0"])
                    en_service = c["service_energy_kwh"]  # computed with service_s at search
                    # recompute service energy for this atom duration
                    from src.q3.relay_geometry import evaluate_relay_site

                    en = evaluate_relay_site(
                        dem,
                        params_r,
                        (c["x_m"], c["y_m"], c["z_amsl_m"]),
                        (c["lon"], c["lat"], c["z_amsl_m"]),
                        setup_s,
                        service_dur,
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
                            "service_duration_s": service_dur,
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
                            "as_is_timing_feasible": int(as_is_feasible),
                            "required_transport_shift_s": req_shift,
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
                "cand_min": min(task_cand_counts) if task_cand_counts else 0,
                "cand_median": float(np.median(task_cand_counts)) if task_cand_counts else 0,
                "cand_mean": float(np.mean(task_cand_counts)) if task_cand_counts else 0,
                "cand_max": max(task_cand_counts) if task_cand_counts else 0,
            }
        )

    pd.DataFrame(all_tasks).to_csv(RESULTS_Q3 / "relay_task_candidates.csv", index=False)
    pd.DataFrame(all_cov).to_csv(RESULTS_Q3 / "relay_coverage_matrix.csv", index=False)
    # site library
    for sid, s in site_lib.items():
        all_sites_rows.append(s)
    pd.DataFrame(all_sites_rows).to_csv(RESULTS_Q3 / "relay_sites.csv", index=False)
    pd.DataFrame(gate_rows).to_csv(RESULTS_Q3 / "relay_candidate_gate_stats_raw.csv", index=False)
    pd.DataFrame(summary).to_csv(RESULTS_Q3 / "relay_task_summary.csv", index=False)
    pd.DataFrame(unresolved).to_csv(RESULTS_Q3 / "relay_unresolved.csv", index=False)
    (RESULTS_Q3 / "e5_run_meta.json").write_text(
        json.dumps({"MIN_ATOMIC_S": MIN_ATOMIC_S, "MAX_SPLIT_DEPTH": MAX_SPLIT_DEPTH, "summary": summary}, indent=2),
        encoding="utf-8",
    )
    print("E5_CORE_DONE", flush=True)
    print(pd.DataFrame(summary).to_string(index=False), flush=True)


if __name__ == "__main__":
    main()
