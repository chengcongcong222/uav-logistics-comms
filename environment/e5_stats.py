#!/usr/bin/env python3
import pandas as pd
from pathlib import Path
Q3 = Path("/home/ccc/projects/uav-logistics-comms/results/q3")
cand = pd.read_csv(Q3 / "relay_task_candidates.csv")
sites = pd.read_csv(Q3 / "relay_sites.csv")
gates = pd.read_csv(Q3 / "relay_candidate_gate_stats_raw.csv")
unres = pd.read_csv(Q3 / "relay_unresolved.csv")
print("sites", len(sites), "pairs", len(cand))
for pid, g in cand.groupby("pareto_id"):
    emin = g.groupby("atomic_task_id").total_energy_kwh.min()
    sh = g.groupby("atomic_task_id").required_transport_shift_s.min()
    print(pid, "tasks", g.atomic_task_id.nunique(), "E_LB", round(float(emin.sum()), 3),
          "zero_shift", int((sh <= 1e-6).sum()), "pos_shift", int((sh > 1e-6).sum()),
          "max_shift", round(float(sh.max()), 2))
agg = gates.groupby("pareto_id")[
    ["raw_3d_candidates", "after_DEM_legality", "after_TR_range", "after_RG_range",
     "after_backhaul", "after_endpoint_access", "after_full_interval_access", "after_energy"]
].sum()
print(agg.to_string())
cnt = cand.groupby(["pareto_id", "atomic_task_id"]).size().reset_index(name="n")
print("tight<=3", int((cnt.n <= 3).sum()), "min", int(cnt.n.min()), "med", float(cnt.n.median()), "max", int(cnt.n.max()))
print("unresolved", len(unres))
