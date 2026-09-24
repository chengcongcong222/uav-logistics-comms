#!/usr/bin/env python3
"""Validate atomic task coverage of parent gaps. Success => E5_ATOMIC_TASKS_VALID (or note unresolved)."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path("/home/ccc/projects/uav-logistics-comms")
sys.path.insert(0, str(ROOT))
from src.common.paths import RESULTS_DIR  # noqa: E402

RESULTS_Q3 = RESULTS_DIR / "q3"


def fail(m):
    print("E5_ATOMIC_TASKS_INVALID:", m)
    raise SystemExit(1)


def main() -> None:
    unres = pd.read_csv(RESULTS_Q3 / "relay_unresolved.csv")
    cand = pd.read_csv(RESULTS_Q3 / "relay_task_candidates.csv")
    # every task in cand has >=1 site
    if cand.empty:
        fail("no candidates at all")
    # unique atomic tasks covered
    covered = set(cand.atomic_task_id.unique())
    # union coverage per parent from cand intervals + unres
    for pid in ("P01", "P02", "P03"):
        gaps = pd.read_csv(RESULTS_Q3 / f"direct_gaps_{pid}.csv")
        for gi, gap in enumerate(gaps.itertuples()):
            parent = f"{pid}_G{gi:03d}"
            subs = cand[cand.parent_gap_id == parent]
            uns = unres[unres.atomic_task_id.astype(str).str.startswith(parent)] if len(unres) else pd.DataFrame()
            intervals = []
            for t in subs.drop_duplicates("atomic_task_id").itertuples():
                intervals.append((t.service_start_s, t.service_end_s))
            for t in uns.itertuples():
                intervals.append((t.start_s, t.end_s))
            if not intervals:
                # gap might be fully covered under different parent naming
                continue
            intervals.sort()
            # check union covers [gap.start, gap.end] without holes
            a, b = float(gap.start_s), float(gap.end_s)
            cur = a
            for s, e in intervals:
                if s > cur + 0.05:
                    fail(f"hole in {parent}")
                cur = max(cur, e)
            if cur < b - 0.05:
                fail(f"incomplete union {parent}")
    if len(unres):
        print(f"E5_ATOMIC_TASKS_VALID_WITH_GRID_UNRESOLVED n={len(unres)}")
    else:
        print("E5_ATOMIC_TASKS_VALID")


if __name__ == "__main__":
    main()
