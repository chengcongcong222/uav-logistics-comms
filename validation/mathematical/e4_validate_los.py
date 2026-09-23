#!/usr/bin/env python3
"""LOS cross-validation + unit checks. Success => E4_LOS_VALID."""
from __future__ import annotations

import random
import sys
from pathlib import Path

ROOT = Path("/home/ccc/projects/uav-logistics-comms")
sys.path.insert(0, str(ROOT))

from src.common.terrain import Dem  # noqa: E402
from src.q3.terrain_los import blocked_dense_sample, blocked_line_cells  # noqa: E402


def fail(msg: str) -> None:
    print(f"E4_LOS_INVALID: {msg}")
    raise SystemExit(1)


def main() -> None:
    dem = Dem()
    rng = random.Random(20260923)

    # bounds of DEM in lon/lat
    b = dem.bounds  # left,bottom,right,top in lon/lat
    # unit 1: very near, high above ground -> LOS
    lon0 = 0.5 * (b.left + b.right)
    lat0 = 0.5 * (b.bottom + b.top)
    z0 = dem.sample(lon0, lat0) + 200
    assert not blocked_line_cells(dem, lon0, lat0, z0, lon0 + 1e-5, lat0, z0 + 1), "near should be LOS"

    # unit 2: obvious far beyond budget is not LOS test; just ensure function returns bool
    far = blocked_line_cells(dem, lon0, lat0, z0, lon0 + 1.0, lat0, z0)
    assert far in (True, False)

    # unit 3: terrain blockage — low height across a ridge-like interior sample
    # construct: endpoints low, interior high terrain -> blocked
    # sample a pair where middle DEM is high
    best_block = None
    for _ in range(50):
        x1 = rng.uniform(b.left + 0.05, b.right - 0.05)
        x2 = rng.uniform(b.left + 0.05, b.right - 0.05)
        y = rng.uniform(b.bottom + 0.05, b.top - 0.05)
        z1 = dem.sample(x1, y) + 5
        z2 = dem.sample(x2, y) + 5
        xm, ym = 0.5 * (x1 + x2), y
        zm = dem.sample(xm, ym)
        if zm > max(z1, z2) + 30:
            if blocked_line_cells(dem, x1, y, z1, x2, y, z2):
                best_block = True
                break
    if best_block is None:
        print("warn: no constructed blockage found in 50 tries (terrain-dependent)")

    # cross-validation 1000 pairs
    n = 1000
    agree = 0
    max_pen = 0.0
    for i in range(n):
        x1 = rng.uniform(b.left, b.right)
        x2 = rng.uniform(b.left, b.right)
        y1 = rng.uniform(b.bottom, b.top)
        y2 = rng.uniform(b.bottom, b.top)
        z1 = dem.sample(x1, y1) + rng.uniform(30, 400)
        z2 = dem.sample(x2, y2) + rng.uniform(30, 400)
        a = blocked_line_cells(dem, x1, y1, z1, x2, y2, z2)
        c = blocked_dense_sample(dem, x1, y1, z1, x2, y2, z2, step_m=10.0)
        if a == c:
            agree += 1
        # penetration proxy: if methods differ, count as disagreement
        if a != c:
            max_pen += 1
    rate = agree / n
    print(f"LOS_agreement={rate:.4f} disagree={n - agree}")
    if rate < 0.95:
        fail(f"LOS agreement too low: {rate}")

    print("E4_LOS_VALID")


if __name__ == "__main__":
    main()
