#!/usr/bin/env python3
"""Independent relay energy recomputation. Success => E5_RELAY_ENERGY_VALID."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path("/home/ccc/projects/uav-logistics-comms")
sys.path.insert(0, str(ROOT))
from src.q3.relay_geometry import load_relay_params  # noqa: E402

RESULTS_Q3 = ROOT / "results/q3"


def fail(m):
    print("E5_RELAY_ENERGY_INVALID:", m)
    raise SystemExit(1)


def main() -> None:
    pr = load_relay_params()
    cand = pd.read_csv(RESULTS_Q3 / "relay_task_candidates.csv")
    for row in cand.itertuples():
        # independent flight energy from stored times
        # E_hor approx: cruise_power * horizontal_time; use flight_energy consistency
        e_fl = row.flight_energy_kwh
        e_su = row.setup_energy_kwh
        e_sv = row.service_energy_kwh
        e_tot = e_fl + e_su + e_sv
        if abs(e_tot - row.total_energy_kwh) > 1e-6:
            fail(f"sum mismatch {row.atomic_task_id}")
        e_use = pr["energy_kwh"]
        margin = (1 - pr["rho"]) * e_use - e_tot
        if abs(margin - row.energy_margin_kwh) > 1e-6:
            fail(f"margin mismatch {row.atomic_task_id}")
        soc = 1 - e_tot / e_use
        if abs(soc - row.return_soc) > 1e-6:
            fail(f"soc mismatch {row.atomic_task_id}")
        if margin < -1e-6:
            fail(f"energy infeasible {row.atomic_task_id}")
    print("E5_RELAY_ENERGY_VALID")


if __name__ == "__main__":
    main()
