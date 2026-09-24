#!/usr/bin/env python3
"""Independent sample check of relay candidates. Success => E5_RELAY_CANDIDATES_VALID."""
from __future__ import annotations

import random
import sys
from pathlib import Path

import pandas as pd

ROOT = Path("/home/ccc/projects/uav-logistics-comms")
sys.path.insert(0, str(ROOT))
from src.common.terrain import Dem
from src.q3.link_budget import load_comm_params, pair_lmax
from src.q3.relay_candidate_generator import access_margin, backhaul_margin
from src.q3.relay_geometry import load_relay_params

RESULTS_Q3 = ROOT / "results/q3"


def fail(m):
    print("E5_RELAY_CANDIDATES_INVALID:", m)
    raise SystemExit(1)


def main() -> None:
    cand = pd.read_csv(RESULTS_Q3 / "relay_task_candidates.csv")
    if cand.empty:
        fail("empty candidates")
    dem = Dem()
    pc, _ = load_comm_params()
    lm = pair_lmax()
    sites = pd.read_csv(RESULTS_Q3 / "relay_sites.csv").set_index("site_id")
    rng = random.Random(20260923)
    checked = 0
    # best-margin and lowest-energy per task
    for aid, g in cand.groupby("atomic_task_id"):
        picks = [g.loc[g.min_twohop_margin_db.idxmax()], g.loc[g.total_energy_kwh.idxmin()]]
        for row in picks:
            sid = row.site_id
            if sid not in sites.index:
                fail(f"missing site {sid}")
            s = sites.loc[sid]
            # recompute backhaul
            mrg, _, _ = backhaul_margin(
                dem,
                pc,
                lm["relay<->G01"],
                {
                    "x_m": s.x_m,
                    "y_m": s.y_m,
                    "lon": s.lon,
                    "lat": s.lat,
                    "z_amsl_m": s.z_amsl_m,
                    "ground_elevation_m": s.ground_elevation_m,
                    "agl_m": s.agl_m,
                    "site_id": sid,
                },
            )
            if mrg < -1e-6:
                fail(f"backhaul {sid}")
            checked += 1
    # 10% random
    sample = cand.sample(n=max(1, int(0.1 * len(cand))), random_state=20260923)
    for row in sample.itertuples():
        s = sites.loc[row.site_id]
        site = {"x_m": s.x_m, "y_m": s.y_m, "lon": s.lon, "lat": s.lat, "z_amsl_m": s.z_amsl_m,
                "ground_elevation_m": s.ground_elevation_m, "agl_m": s.agl_m, "site_id": row.site_id}
        mrg, _, _ = backhaul_margin(dem, pc, lm["relay<->G01"], site)
        if mrg < -1e-6:
            fail(f"sample backhaul {row.site_id}")
    print("E5_RELAY_CANDIDATES_VALID", checked)


if __name__ == "__main__":
    main()
