#!/usr/bin/env python3
"""Generate E0 test trajectory CSV for ns-3 WaypointMobilityModel import."""
from __future__ import annotations

from pathlib import Path

import pandas as pd


def main() -> None:
    root = Path("/home/ccc/projects/huawei-cup-d")
    export_dir = root / "export"
    export_dir.mkdir(parents=True, exist_ok=True)
    out = export_dir / "e0_test_trace.csv"

    rows = [
        {"node_id": "G01", "time": 0, "x": 0, "y": 0, "z": 0},
        {"node_id": "U01", "time": 0, "x": 0, "y": 0, "z": 50},
        {"node_id": "U01", "time": 10, "x": 100, "y": 0, "z": 50},
        {"node_id": "U01", "time": 20, "x": 200, "y": 0, "z": 50},
    ]
    df = pd.DataFrame(rows, columns=["node_id", "time", "x", "y", "z"])
    df.to_csv(out, index=False)
    print(f"wrote {out}")
    print(df.to_string(index=False))


if __name__ == "__main__":
    main()
