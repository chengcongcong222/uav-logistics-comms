#!/usr/bin/env python3
"""Validate true 4-objective nondominated set. Success => E3_PARETO_VALID."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path("/home/ccc/projects/uav-logistics-comms")
sys.path.insert(0, str(ROOT))

from src.common.paths import RESULTS_Q2  # noqa: E402

COLS = ["J_time", "makespan", "energy", "sorties"]


def fail(msg: str) -> None:
    print(f"E3_PARETO_INVALID: {msg}")
    raise SystemExit(1)


def dominates(a, b) -> bool:
    """a dominates b if all <= and any <."""
    le = all(a[c] <= b[c] + 1e-12 for c in COLS)
    lt = any(a[c] < b[c] - 1e-12 for c in COLS)
    return le and lt


def main() -> None:
    p = RESULTS_Q2 / "q2_pareto.csv"
    df = pd.read_csv(p)
    if df.empty:
        fail("empty pareto")
    for c in COLS:
        if c not in df.columns:
            fail(f"missing column {c}")
    recs = df[COLS].to_dict("records")
    for i, a in enumerate(recs):
        for j, b in enumerate(recs):
            if i == j:
                continue
            if dominates(a, b):
                fail(f"row {j} dominated by row {i}: {a} vs {b}")
    # no duplicate rows
    if df.duplicated(subset=COLS).any():
        fail("duplicate points in pareto")
    print("E3_PARETO_VALID")


if __name__ == "__main__":
    main()
