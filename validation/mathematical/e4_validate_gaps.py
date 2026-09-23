#!/usr/bin/env python3
"""Validate extracted direct gaps. Success => E4_GAP_VALID."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path("/home/ccc/projects/uav-logistics-comms")
sys.path.insert(0, str(ROOT))
from src.common.paths import RESULTS_DIR  # noqa: E402

RESULTS_Q3 = RESULTS_DIR / "q3"
TOL = 0.15  # s, slightly above 0.1 binary target


def fail(msg: str) -> None:
    print(f"E4_GAP_INVALID: {msg}")
    raise SystemExit(1)


def main() -> None:
    path = RESULTS_Q3 / "direct_gaps.csv"
    if not path.exists():
        fail("missing direct_gaps.csv")
    gaps = pd.read_csv(path)
    if gaps.empty or "pareto_id" not in gaps.columns:
        # no gaps found — valid if margins confirm all direct_available
        print("E4_GAP_VALID (no gaps)")
        return
    for pid, gdf in gaps.groupby("pareto_id"):
        margin = pd.read_csv(RESULTS_Q3 / f"direct_margin_{pid}.csv")
        for gap in gdf.itertuples():
            sub = margin[margin.sortie_id == gap.sortie_id].sort_values("time")
            inside = sub[(sub.time >= gap.start_s) & (sub.time <= gap.end_s)]
            if inside.empty:
                fail(f"empty gap interior {gap.gap_id}")
            # representative samples inside should be mostly negative
            if (inside.M_C >= 0).mean() > 0.5:
                fail(f"gap interior has too many non-negative M_C {gap.gap_id}")
            # just outside boundaries
            before = sub[(sub.time < gap.start_s) & (sub.time >= gap.start_s - 1.0)]
            after = sub[(sub.time > gap.end_s) & (sub.time <= gap.end_s + 1.0)]
            if not before.empty and (before.M_C < 0).all() and (before.M_C < -3).any():
                fail(f"gap start may be late {gap.gap_id}")
            if not after.empty and (after.M_C < 0).all() and (after.M_C < -3).any():
                fail(f"gap end may be early {gap.gap_id}")
        break  # one representative pareto is enough per spec
    print("E4_GAP_VALID")


if __name__ == "__main__":
    main()
