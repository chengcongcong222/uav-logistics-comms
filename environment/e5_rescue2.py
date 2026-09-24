#!/usr/bin/env python3
"""Final rescue: sample sites around transport samples for still-unresolved atoms."""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, "/home/ccc/projects/uav-logistics-comms")
from src.common.terrain import Dem
from src.q3.link_budget import load_comm_params, pair_lmax
from src.q3.relay_candidate_generator import access_margin, backhaul_margin, make_site
from src.q3.relay_geometry import evaluate_relay_site, load_relay_params

ROOT = Path("/home/ccc/projects/uav-logistics-comms")
Q3 = ROOT / "results/q3"
unres = pd.read_csv(Q3 / "relay_unresolved.csv")
dem = Dem()
pc, _ = load_comm_params()
pr = load_relay_params()
lm = pair_lmax()
site_lib = {}
new_tasks = []
new_cov = []

for _, r in unres.iterrows():
    margin = pd.read_csv(Q3 / f"direct_margin_{r.pareto_id}.csv")
    sub = margin[(margin.time >= r.start_s) & (margin.time <= r.end_s)]
    if sub.empty:
        continue
    service = r.end_s - r.start_s
    found = []
    for _, p in sub.iloc[:: max(1, len(sub) // 5)].iterrows():
        for ang in range(0, 360, 45):
            for rad in (150, 300, 500, 800):
                x = p.x + rad * math.cos(math.radians(ang))
                y = p.y + rad * math.sin(math.radians(ang))
                for agl in (50, 100, 150, 200, 250, 300):
                    site = make_site(dem, x, y, float(agl), pr["setup_time_s"], service)
                    if not site:
                        continue
                    mrg, _, _ = backhaul_margin(dem, pc, lm["relay<->G01"], site)
                    if mrg < 0:
                        continue
                    min_mur = 1e9
                    ok = True
                    for _, q in sub.iloc[:: max(1, len(sub) // 6)].iterrows():
                        mur, _, _ = access_margin(dem, pc, lm["transport<->relay"], site, (q.x, q.y, q.z))
                        min_mur = min(min_mur, mur)
                        if min_mur < 0:
                            ok = False
                            break
                    if not ok:
                        continue
                    en = evaluate_relay_site(dem, pr, (site["x_m"], site["y_m"], site["z_amsl_m"]), (site["lon"], site["lat"], site["z_amsl_m"]), pr["setup_time_s"], service)
                    if en["energy_margin_kwh"] < 0:
                        continue
                    found.append((site, min_mur, mrg, en))
                    if len(found) >= 5:
                        break
                if len(found) >= 5:
                    break
            if len(found) >= 5:
                break
        if len(found) >= 5:
            break
    print(r.atomic_task_id, "found", len(found), flush=True)
    for site, min_mur, mrg, en in found:
        new_tasks.append(
            {
                "pareto_id": r.pareto_id,
                "atomic_task_id": r.atomic_task_id,
                "parent_gap_id": str(r.atomic_task_id).rsplit("_A", 1)[0],
                "transport_sortie_id": "",
                "site_id": site["site_id"],
                "service_start_s": r.start_s,
                "service_end_s": r.end_s,
                "service_duration_s": service,
                "min_access_margin_db": min_mur,
                "backhaul_margin_db": mrg,
                "min_twohop_margin_db": min(min_mur, mrg),
                "outbound_time_s": en["outbound_time_s"],
                "return_time_s": en["return_time_s"],
                "setup_time_s": pr["setup_time_s"],
                "flight_energy_kwh": en["flight_energy_kwh"],
                "setup_energy_kwh": en["setup_energy_kwh"],
                "service_energy_kwh": en["service_energy_kwh"],
                "total_energy_kwh": en["total_energy_kwh"],
                "energy_margin_kwh": en["energy_margin_kwh"],
                "return_soc": en["return_soc"],
                "earliest_ready_s": pr["prep_time_s"] + en["outbound_time_s"] + pr["setup_time_s"],
                "as_is_timing_feasible": int(r.start_s >= pr["prep_time_s"] + en["outbound_time_s"] + pr["setup_time_s"]),
                "required_transport_shift_s": max(0.0, pr["prep_time_s"] + en["outbound_time_s"] + pr["setup_time_s"] - r.start_s),
            }
        )
        new_cov.append({"site_id": site["site_id"], "atomic_task_id": r.atomic_task_id, "feasible": 1,
                        "min_twohop_margin_db": min(min_mur, mrg), "total_energy_kwh": en["total_energy_kwh"]})

if new_tasks:
    old = pd.read_csv(Q3 / "relay_task_candidates.csv")
    pd.concat([old, pd.DataFrame(new_tasks)], ignore_index=True).to_csv(Q3 / "relay_task_candidates.csv", index=False)
    oldc = pd.read_csv(Q3 / "relay_coverage_matrix.csv")
    pd.concat([oldc, pd.DataFrame(new_cov)], ignore_index=True).to_csv(Q3 / "relay_coverage_matrix.csv", index=False)
still = []
for _, r in unres.iterrows():
    if sum(1 for t in new_tasks if t["atomic_task_id"] == r.atomic_task_id) == 0:
        still.append(r.to_dict())
pd.DataFrame(still).to_csv(Q3 / "relay_unresolved.csv", index=False)
print("still", len(still))
print("E5_RESCUE2_DONE")
