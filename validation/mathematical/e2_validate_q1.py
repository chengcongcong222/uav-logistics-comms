#!/usr/bin/env python3
"""E2 Q1 validation. Prints E2_Q1_OK on success."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path("/home/ccc/projects/uav-logistics-comms")
sys.path.insert(0, str(ROOT))


def main() -> None:
    mp = pd.read_csv(ROOT / "results/q1/max_safe_payload.csv")
    pk = pd.read_csv(ROOT / "results/q1/q1_packings_rho20.csv")
    boxes = pd.read_csv(ROOT / "data/processed/boxes.csv")

    assert len(mp) == 3 * 15, len(mp)
    assert (mp.payload_limit_kg >= 0).all()
    assert (mp.payload_limit_kg <= 80 + 1e-6).all()

    # packing covers every box exactly once at its service
    assigned = []
    for _, r in pk.iterrows():
        ids = eval(r.box_ids) if isinstance(r.box_ids, str) else r.box_ids
        assigned.extend(ids)
    assert len(assigned) == len(set(assigned)) == len(boxes)
    assert set(assigned) == set(boxes.box_id)

    # no cross-service packing
    bmap = boxes.set_index("box_id")["service_id"].to_dict()
    for _, r in pk.iterrows():
        ids = eval(r.box_ids) if isinstance(r.box_ids, str) else r.box_ids
        assert all(bmap[b] == r.service_id for b in ids)

    assert pk.energy_kwh.min() > 0
    assert pk.time_s.min() > 0
    print(f"packings={len(pk)} boxes={len(assigned)}")
    print("E2_Q1_OK")


if __name__ == "__main__":
    main()
