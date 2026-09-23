"""Analyze Q2 Pareto transport plans under direct communication (P01-P04)."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.common.paths import RESULTS_DIR, RESULTS_Q2
from src.common.terrain import Dem
from src.q3.gap_extractor import build_adaptive_series, extract_gaps
from src.q3.link_budget import build_link_budget_table, max_range_m, load_comm_params
from src.q3.trajectory import g01_position

RESULTS_Q3 = RESULTS_DIR / "q3"
PARETO_DIR = RESULTS_Q2 / "pareto_schedules"


def analyze_one(pid: str, dem: Dem, g01) -> dict:
    pdir = PARETO_DIR / pid
    trace = pd.read_csv(pdir / "transport_trace.csv")
    sorties = pd.read_csv(pdir / "q2_sorties.csv")
    margin = build_adaptive_series(trace, dem, g01, pid)
    margin.to_csv(RESULTS_Q3 / f"direct_margin_{pid}.csv", index=False)
    gaps = extract_gaps(margin)
    if not gaps.empty:
        gaps.insert(0, "pareto_id", pid)
    gaps.to_csv(RESULTS_Q3 / f"direct_gaps_{pid}.csv", index=False)

    # merge gaps later
    t0 = float(margin.time.min())
    t1 = float(margin.time.max())
    span = max(t1 - t0, 1e-9)
    # activity is per-sortie takeoff..return; ratio over union of active time
    active = 0.0
    avail = 0.0
    for sid, g in margin.groupby("sortie_id"):
        g = g.sort_values("time")
        a0, a1 = float(g.time.min()), float(g.time.max())
        active += a1 - a0
        # approximate available time by trapezoid of indicator
        av = 0.0
        for i in range(len(g) - 1):
            dt = float(g.time.iloc[i + 1] - g.time.iloc[i])
            ok = 1.0 if (g.direct_available.iloc[i] + g.direct_available.iloc[i + 1]) >= 1 else 0.0
            av += ok * dt
        avail += av

    gap_dur = float(gaps.duration_s.sum()) if not gaps.empty else 0.0
    n_gaps = int(len(gaps))
    max_gap = float(gaps.duration_s.max()) if not gaps.empty else 0.0
    sorties_with_gap = int(gaps.sortie_id.nunique()) if not gaps.empty else 0
    min_m = float(margin.M_C.min()) if not margin.empty else None
    terrain_dur = float(gaps.loc[gaps.cause.isin(["TERRAIN_BLOCKAGE", "DISTANCE_AND_BLOCKAGE"]), "duration_s"].sum()) if not gaps.empty else 0.0
    dist_dur = float(gaps.loc[gaps.cause.isin(["DISTANCE_ONLY", "DISTANCE_AND_BLOCKAGE"]), "duration_s"].sum()) if not gaps.empty else 0.0

    return {
        "pareto_id": pid,
        "transport_sorties": int(len(sorties)),
        "direct_available_time_ratio": (avail / active) if active > 0 else None,
        "n_direct_gaps": n_gaps,
        "total_gap_duration_s": gap_dur,
        "max_single_gap_s": max_gap,
        "sorties_requiring_relay": sorties_with_gap,
        "min_direct_margin_db": min_m,
        "terrain_caused_gap_s": terrain_dur,
        "distance_caused_gap_s": dist_dur,
        "active_time_s": active,
    }


def main() -> None:
    RESULTS_Q3.mkdir(parents=True, exist_ok=True)
    # link budget file
    build_link_budget_table().to_csv(RESULTS_Q3 / "link_budget.csv", index=False)
    params, _ = load_comm_params()
    tb = build_link_budget_table().set_index("pair")
    ranges = []
    for pair, r in tb.iterrows():
        ranges.append(
            {
                "pair": pair,
                "L_max_db": r.L_max_db,
                "D_los_m": max_range_m(r.L_max_db, params, False),
                "D_obs_m": max_range_m(r.L_max_db, params, True),
            }
        )
    pd.DataFrame(ranges).to_csv(RESULTS_Q3 / "theoretical_ranges.csv", index=False)

    dem = Dem()
    g01 = g01_position()
    rows = []
    all_gaps = []
    for pid in ("P01", "P02", "P03", "P04"):
        if not (PARETO_DIR / pid / "transport_trace.csv").exists():
            print("missing", pid, flush=True)
            continue
        print("analyze", pid, flush=True)
        rows.append(analyze_one(pid, dem, g01))
        g = pd.read_csv(RESULTS_Q3 / f"direct_gaps_{pid}.csv")
        all_gaps.append(g)
    pd.DataFrame(rows).to_csv(RESULTS_Q3 / "q2_pareto_communication_burden.csv", index=False)
    if all_gaps:
        pd.concat(all_gaps, ignore_index=True).to_csv(RESULTS_Q3 / "direct_gaps.csv", index=False)
    print("ANALYZE_DONE", flush=True)


if __name__ == "__main__":
    main()
