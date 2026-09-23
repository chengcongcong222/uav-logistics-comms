#!/usr/bin/env bash
set -euo pipefail
cd /home/ccc/projects/uav-logistics-comms
.venv/bin/python validation/mathematical/e2_validate_q1.py
.venv/bin/python validation/mathematical/e2_validate_physics.py
echo "==== max_safe_payload head ===="
head -20 results/q1/max_safe_payload.csv
echo "==== packings ===="
cat results/q1/q1_packings_rho20.csv
echo "==== sensitivity packing summary ===="
.venv/bin/python - <<'PY'
import pandas as pd
s = pd.read_csv("results/q1/reserve_sensitivity.csv")
print(s[s.kind == "packing_summary"].to_string(index=False))
mp = s[s.kind == "max_payload"]
print(mp.groupby(["rho", "binding_constraint"]).size())
print("payload stats by type rho=0.2")
print(mp[mp.rho == 0.2].groupby("uav_type")["payload_limit_kg"].describe()[["min", "max", "mean"]])
PY
