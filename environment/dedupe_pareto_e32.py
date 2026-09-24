#!/usr/bin/env python3
"""Dedupe E3.2 Pareto schedules to unique metric points P01..PK."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pandas as pd

ROOT = Path("/home/ccc/projects/uav-logistics-comms")
PAR = ROOT / "results/q2/pareto_schedules"


def main() -> None:
    # collect unique metadata among P*
    seen = {}
    order = []
    for pdir in sorted(PAR.glob("P*")):
        meta = json.loads((pdir / "metadata.json").read_text(encoding="utf-8"))
        key = (
            round(float(meta["J_late"]), 6),
            round(float(meta["J_norm"]), 8),
            round(float(meta["makespan"]), 3),
            round(float(meta["energy"]), 6),
            int(meta["sorties"]),
        )
        if key not in seen:
            seen[key] = pdir
            order.append(key)
        else:
            shutil.rmtree(pdir, ignore_errors=True)
    # rename remaining
    for i, key in enumerate(order, 1):
        src = seen[key]
        dst = PAR / f"P{i:02d}"
        if src != dst:
            if dst.exists():
                shutil.rmtree(dst, ignore_errors=True)
            src.rename(dst)
        meta = json.loads((dst / "metadata.json").read_text(encoding="utf-8"))
        meta["pareto_id"] = f"P{i:02d}"
        meta["tag"] = f"P{i:02d}"
        (dst / "metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
        print(f"P{i:02d}", meta["J_late"], meta["J_norm"], meta["makespan"], meta["energy"], meta["sorties"])
    # rewrite q2_pareto_e32 unique
    rows = []
    for i, key in enumerate(order, 1):
        meta = json.loads((PAR / f"P{i:02d}" / "metadata.json").read_text(encoding="utf-8"))
        rows.append(
            {
                "pareto_id": f"P{i:02d}",
                "J_late": meta["J_late"],
                "J_norm": meta["J_norm"],
                "makespan": meta["makespan"],
                "energy": meta["energy"],
                "sorties": meta["sorties"],
            }
        )
    pd.DataFrame(rows).to_csv(ROOT / "results/q2/q2_pareto_e32.csv", index=False)
    print("K", len(rows))


if __name__ == "__main__":
    main()
