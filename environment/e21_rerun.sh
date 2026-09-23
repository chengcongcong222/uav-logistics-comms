#!/usr/bin/env bash
set -euo pipefail
cd /home/ccc/projects/uav-logistics-comms
mkdir -p results/e2
{
  echo "==== e2_validate_physics ===="
  .venv/bin/python validation/mathematical/e2_validate_physics.py
  echo "==== solve_q1 ===="
  .venv/bin/python -m src.q1.solve_q1
  echo "==== e2_validate_q1 ===="
  .venv/bin/python validation/mathematical/e2_validate_q1.py
  echo "==== summarize ===="
  .venv/bin/python - <<'PY'
import pandas as pd
mp = pd.read_csv("results/q1/max_safe_payload.csv")
pk = pd.read_csv("results/q1/q1_packings_rho20.csv")
s = pd.read_csv("results/q1/reserve_sensitivity.csv")
print("payload_limit by type:")
print(mp.groupby("uav_type")["payload_limit_kg"].agg(["min", "max", "mean"]))
print("hardest rows (min payload per type):")
print(mp.loc[mp.groupby("uav_type")["payload_limit_kg"].idxmin()][
    ["uav_type", "service_id", "payload_limit_kg", "binding_constraint", "roundtrip_energy_kwh"]
])
print("packings:", len(pk), "total_energy:", pk.energy_kwh.sum(), "total_time:", pk.time_s.sum())
print(s[s.kind == "packing_summary"][
    ["rho", "n_flights", "total_energy_kwh", "total_time_s"]
].to_string(index=False))
print(s[s.kind == "max_payload"].groupby(["rho", "binding_constraint"]).size())
PY
  echo "ALL_DONE"
} > results/e2/e21_rerun.log 2>&1
echo EXIT:$?
tail -n 60 results/e2/e21_rerun.log
