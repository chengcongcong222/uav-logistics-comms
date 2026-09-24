#!/usr/bin/env python3
"""Rescue GRID_UNRESOLVED atomic tasks with denser 30m/25m search."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, "/home/ccc/projects/uav-logistics-comms")
from src.common.terrain import Dem
from src.q3.e5_relay_tasks import search_sites_for_interval
from src.q3.link_budget import load_comm_params, pair_lmax
from src.q3.relay_geometry import load_relay_params

ROOT = Path("/home/ccc/projects/uav-logistics-comms")
Q3 = ROOT / "results/q3"

unres = pd.read_csv(Q3 / "relay_unresolved.csv")
if unres.empty:
    print("no unresolved")
    raise SystemExit(0)
dem = Dem()
pc, _ = load_comm_params()
pr = load_relay_params()
lm = pair_lmax()
site_lib = {}
tasks = []
cov = []
for _, r in unres.iterrows():
    margin = pd.read_csv(Q3 / f"direct_margin_{r.pareto_id}.csv")
    service = r.end_s - r.start_s
    cands, gate = search_sites_for_interval(dem, pc, pr, lm, margin, r.start_s, r.end_s, site_lib, pr["setup_time_s"], max(service, 10.0))
    print(r.atomic_task_id, "cands", len(cands), flush=True)
    for c in cands:
        tasks.append(
            {
                "pareto_id": r.pareto_id,
                "atomic_task_id": r.atomic_task_id,
                "parent_gap_id": r.atomic_task_id.rsplit("_A", 1)[0],
                "transport_sortie_id": "",
                "site_id": c["site_id"],
                "service_start_s": r.start_s,
                "service_end_s": r.end_s,
                "service_duration_s": service,
                "min_access_margin_db": c["min_access_margin_db"],
                "backhaul_margin_db": c["backhaul_margin_db"],
                "min_twohop_margin_db": c["min_twohop_margin_db"],
                "outbound_time_s": c["outbound_time_s"],
                "return_time_s": c["return_time_s"],
                "setup_time_s": pr["setup_time_s"],
                "flight_energy_kwh": c["flight_energy_kwh"],
                "setup_energy_kwh": c["setup_energy_kwh"],
                "service_energy_kwh": c["service_energy_kwh"],
                "total_energy_kwh": c["total_energy_kwh"],
                "energy_margin_kwh": c["energy_margin_kwh"],
                "return_soc": c["return_soc"],
                "earliest_ready_s": pr["prep_time_s"] + c["outbound_time_s"] + pr["setup_time_s"],
                "as_is_timing_feasible": int(r.start_s >= pr["prep_time_s"] + c["outbound_time_s"] + pr["setup_time_s"]),
                "required_transport_shift_s": max(0.0, pr["prep_time_s"] + c["outbound_time_s"] + pr["setup_time_s"] - r.start_s),
            }
        )
        cov.append({"site_id": c["site_id"], "atomic_task_id": r.atomic_task_id, "feasible": 1,
                    "min_twohop_margin_db": c["min_twohop_margin_db"], "total_energy_kwh": c["total_energy_kwh"]})

if tasks:
    old = pd.read_csv(Q3 / "relay_task_candidates.csv")
    pd.concat([old, pd.DataFrame(tasks)], ignore_index=True).to_csv(Q3 / "relay_task_candidates.csv", index=False)
    oldc = pd.read_csv(Q3 / "relay_coverage_matrix.csv")
    pd.concat([oldc, pd.DataFrame(cov)], ignore_index=True).to_csv(Q3 / "relay_coverage_matrix.csv", index=False)
# remaining unresolved
still = []
for _, r in unres.iterrows():
    n = sum(1 for t in tasks if t["atomic_task_id"] == r.atomic_task_id)
    if n == 0:
        still.append(r.to_dict())
pd.DataFrame(still).to_csv(Q3 / "relay_unresolved.csv", index=False)
print("still_unresolved", len(still))
print("E5_RESCUE_DONE")
