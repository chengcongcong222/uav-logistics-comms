#!/usr/bin/env python3
"""E3.2 Pareto validator under TimelinessKey dominance."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path("/home/ccc/projects/uav-logistics-comms")
sys.path.insert(0, str(ROOT))
from src.common.paths import RESULTS_Q2  # noqa: E402


def fail(msg: str) -> None:
    print(f"E32_PARETO_INVALID: {msg}")
    raise SystemExit(1)


def dominates(a: dict, b: dict) -> bool:
    ta = (float(a["J_late"]), float(a["J_norm"]))
    tb = (float(b["J_late"]), float(b["J_norm"]))
    tim_le = (ta[0] < tb[0] - 1e-9) or (abs(ta[0] - tb[0]) <= 1e-9 and ta[1] <= tb[1] + 1e-12)
    le = all(float(a[c]) <= float(b[c]) + 1e-9 for c in ("makespan", "energy", "sorties"))
    strict = (ta[0] < tb[0] - 1e-9) or (abs(ta[0] - tb[0]) <= 1e-9 and ta[1] < tb[1] - 1e-12) or any(
        float(a[c]) < float(b[c]) - 1e-9 for c in ("makespan", "energy", "sorties")
    )
    return tim_le and le and strict


def main() -> None:
    p = RESULTS_Q2 / "q2_pareto_e32.csv"
    if not p.exists():
        fail("missing q2_pareto_e32.csv")
    df = pd.read_csv(p)
    if df.empty:
        fail("empty pareto")
    recs = df.to_dict("records")
    for i, a in enumerate(recs):
        for j, b in enumerate(recs):
            if i != j and dominates(a, b):
                fail(f"{i} dominates {j}")
    print("E32_PARETO_VALID")


if __name__ == "__main__":
    main()
