#!/usr/bin/env bash
set -euo pipefail
cd /home/ccc/projects/uav-logistics-comms
.venv/bin/python - <<'PY'
import pandas as pd
mp = pd.read_csv("results/q1/max_safe_payload.csv")
for g, s in [("C", "S003"), ("C", "S004"), ("B", "S008"), ("C", "S008")]:
    row = mp[(mp.uav_type == g) & (mp.service_id == s)].iloc[0]
    print(f"{g}-{s}: {row.payload_limit_kg:.4f} kg  {row.binding_constraint}  E={row.roundtrip_energy_kwh:.4f}")
print("A all unique", mp[mp.uav_type == "A"].payload_limit_kg.unique())
print("B min", mp[mp.uav_type == "B"].payload_limit_kg.min())
print("C min", mp[mp.uav_type == "C"].payload_limit_kg.min())
PY
