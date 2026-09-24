#!/usr/bin/env python3
"""Validate each Pxx schedule package. Success => E32_PARETO_SCHEDULES_VALID."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pandas as pd

ROOT = Path("/home/ccc/projects/uav-logistics-comms")
sys.path.insert(0, str(ROOT))
from src.common.paths import RESULTS_Q2  # noqa: E402


def fail(msg: str) -> None:
    print(f"E32_PARETO_SCHEDULES_INVALID: {msg}")
    raise SystemExit(1)


def main() -> None:
    pdirs = sorted((RESULTS_Q2 / "pareto_schedules").glob("P*"))
    if not pdirs:
        fail("no Pxx schedules")
    for pdir in pdirs:
        for req in (
            "q2_sorties.csv",
            "q2_box_delivery.csv",
            "q2_uav_calendar.csv",
            "q2_battery_calendar.csv",
            "transport_trace.csv",
            "missions.json",
            "metadata.json",
        ):
            if not (pdir / req).exists():
                fail(f"{pdir.name} missing {req}")
        boxes = pd.read_csv(pdir / "q2_box_delivery.csv")
        if len(boxes) != 80 or boxes.box_id.nunique() != 80:
            fail(f"{pdir.name} box coverage")
        meta = json.loads((pdir / "metadata.json").read_text(encoding="utf-8"))
        # hard deadlines
        if "hard_deadline_ok" in boxes.columns and not boxes.hard_deadline_ok.fillna(True).all():
            fail(f"{pdir.name} hard deadline")
        print(f"{pdir.name} package_ok late={meta.get('J_late')} N={meta.get('sorties')}", flush=True)
    print("E32_PARETO_SCHEDULES_VALID")


if __name__ == "__main__":
    main()
