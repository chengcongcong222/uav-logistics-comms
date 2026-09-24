#!/usr/bin/env python3
"""Check E4 report numbers match burden CSV. Success => E4_REPORT_CONSISTENT."""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path("/home/ccc/projects/uav-logistics-comms")
sys.path.insert(0, str(ROOT))
from src.common.paths import RESULTS_DIR  # noqa: E402

RESULTS_Q3 = RESULTS_DIR / "q3"


def fail(msg: str) -> None:
    print(f"E4_REPORT_INVALID: {msg}")
    raise SystemExit(1)


def main() -> None:
    report = (RESULTS_Q3 / "E4_COMMUNICATION_REPORT.md").read_text(encoding="utf-8")
    burden = pd.read_csv(RESULTS_Q3 / "q2_pareto_communication_burden.csv")
    for r in burden.itertuples():
        pid = r.pareto_id
        # require key numbers appear (gap_count, rounded gap time)
        if str(int(r.gap_count)) not in report:
            fail(f"{pid} gap_count {int(r.gap_count)} not in report")
        # round gap duration to integer seconds
        if str(int(round(r.direct_gap_time_s))) not in report and f"{r.direct_gap_time_s:.0f}" not in report:
            # allow one of the formatted forms
            if f"{int(r.direct_gap_time_s):,}" not in report and str(int(r.direct_gap_time_s)) not in report:
                fail(f"{pid} gap_time {r.direct_gap_time_s} not in report")
    if "E4_Q3_COMMUNICATION_READY" not in report:
        fail("missing READY token")
    print("E4_REPORT_CONSISTENT")


if __name__ == "__main__":
    main()
