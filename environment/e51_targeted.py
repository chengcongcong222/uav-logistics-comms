#!/usr/bin/env python3
"""E5.1 targeted deep-split for previously unresolved atoms only."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, "/home/ccc/projects/uav-logistics-comms")
from src.common.terrain import Dem
from src.q3.e51_relay_tasks import split_task
from src.q3.link_budget import load_comm_params, pair_lmax
from src.q3.relay_geometry import evaluate_relay_site, load_relay_params

ROOT = Path("/home/ccc/projects/uav-logistics-comms")
Q3 = ROOT / "results/q3"
unres = pd.read_csv(Q3 / "relay_unresolved.csv")
print("before", len(unres), flush=True)
dem = Dem()
pc, _ = load_comm_params()
pr = load_relay_params()
lm = pair_lmax()
new_tasks, new_cov, still = [], [], []
summary_rows = []

for _, r in unres.iterrows():
    margin = pd.read_csv(Q3 / f"direct_margin_{r.pareto_id}.csv")
    print("atom", r.atomic_task_id, float(r.start_s), float(r.end_s), flush=True)
    atoms, gate, unresolved = split_task(
        dem, pc, pr, lm, margin, float(r.start_s), float(r.end_s), pr["setup_time_s"]
    )
    print("  parts", len(atoms), "unres_flag", unresolved, flush=True)
    parent = str(r.atomic_task_id).rsplit("_A", 1)[0]
    for ai, atom in enumerate(atoms):
        aid = f"{parent}_R{ai:02d}"
        service = atom["t1"] - atom["t0"]
        if not atom["cands"]:
            still.append(
                {
                    "pareto_id": r.pareto_id,
                    "atomic_task_id": aid,
                    "start_s": atom["t0"],
                    "end_s": atom["t1"],
                    "note": "GRID_UNRESOLVED",
                }
            )
            continue
        for c in atom["cands"]:
            en = evaluate_relay_site(
                dem,
                pr,
                (c["x_m"], c["y_m"], c["z_amsl_m"]),
                (c["lon"], c["lat"], c["z_amsl_m"]),
                pr["setup_time_s"],
                service,
            )
            lead = pr["prep_time_s"] + c["outbound_time_s"] + pr["setup_time_s"]
            new_tasks.append(
                {
                    "pareto_id": r.pareto_id,
                    "atomic_task_id": aid,
                    "parent_gap_id": parent,
                    "transport_sortie_id": "",
                    "site_id": c["site_id"],
                    "service_start_s": atom["t0"],
                    "service_end_s": atom["t1"],
                    "service_duration_s": service,
                    "min_access_margin_db": c["min_access_margin_db"],
                    "backhaul_margin_db": c["backhaul_margin_db"],
                    "min_twohop_margin_db": c["min_twohop_margin_db"],
                    "outbound_time_s": c["outbound_time_s"],
                    "return_time_s": c["return_time_s"],
                    "setup_time_s": pr["setup_time_s"],
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
            new_cov.append(
                {
                    "site_id": c["site_id"],
                    "atomic_task_id": aid,
                    "feasible": 1,
                    "min_twohop_margin_db": c["min_twohop_margin_db"],
                    "total_energy_kwh": en["total_energy_kwh"],
                }
            )
    summary_rows.append(
        {
            "atomic_task_id": r.atomic_task_id,
            "parts": len(atoms),
            "resolved_parts": sum(1 for a in atoms if a["cands"]),
        }
    )

if new_tasks:
    old = pd.read_csv(Q3 / "relay_task_candidates.csv")
    pd.concat([old, pd.DataFrame(new_tasks)], ignore_index=True).to_csv(
        Q3 / "relay_task_candidates.csv", index=False
    )
    oldc = pd.read_csv(Q3 / "relay_coverage_matrix.csv")
    pd.concat([oldc, pd.DataFrame(new_cov)], ignore_index=True).to_csv(
        Q3 / "relay_coverage_matrix.csv", index=False
    )
pd.DataFrame(still).to_csv(Q3 / "relay_unresolved.csv", index=False)
pd.DataFrame(summary_rows).to_csv(Q3 / "e51_unresolved_resolution.csv", index=False)
print("after_unresolved", len(still), flush=True)
print("E51_TARGETED_DONE", flush=True)
