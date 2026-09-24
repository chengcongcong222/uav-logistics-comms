#!/usr/bin/env python3
"""Independent gap boundary checks for all Pxx. Success => E41_GAPS_VALID."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path("/home/ccc/projects/uav-logistics-comms")
sys.path.insert(0, str(ROOT))
from src.common.paths import RESULTS_DIR, RESULTS_Q2  # noqa: E402
from src.common.terrain import Dem  # noqa: E402
from src.q3.gap_e41 import margin_at  # noqa: E402
from src.q3.link_budget import load_comm_params, pair_lmax  # noqa: E402
from src.q3.trajectory import g01_position  # noqa: E402

RESULTS_Q3 = RESULTS_DIR / "q3"
DELTA = 0.2


def fail(msg: str) -> None:
    print(f"E41_GAPS_INVALID: {msg}")
    raise SystemExit(1)


def main() -> None:
    dem = Dem()
    params, _ = load_comm_params()
    l_max = pair_lmax()["transport<->G01"]
    g01 = g01_position()
    from pyproj import Transformer
    from src.common.schemas import EPSG_UTM49N, EPSG_WGS84

    tf = Transformer.from_crs(EPSG_UTM49N, EPSG_WGS84, always_xy=True)
    glon, glat = tf.transform(g01[0], g01[1])
    g_ll = (glon, glat, g01[2])

    gaps = pd.read_csv(RESULTS_Q3 / "direct_gaps.csv")
    if gaps.empty:
        print("E41_GAPS_VALID (none)")
        return
    for pid, gdf in gaps.groupby("pareto_id"):
        margin = pd.read_csv(RESULTS_Q3 / f"direct_margin_{pid}.csv")
        for gap in gdf.itertuples():
            sub = margin[margin.sortie_id == gap.sortie_id].sort_values("time")

            def mc_near(t):
                # interpolate position from margin samples
                if t <= sub.time.iloc[0]:
                    r = sub.iloc[0]
                elif t >= sub.time.iloc[-1]:
                    r = sub.iloc[-1]
                else:
                    # linear between neighbors
                    import numpy as np

                    x = np.interp(t, sub.time, sub.x)
                    y = np.interp(t, sub.time, sub.y)
                    z = np.interp(t, sub.time, sub.z)
                    return margin_at(dem, params, l_max, g01, g_ll, x, y, z)[0]
                return margin_at(dem, params, l_max, g01, g_ll, r.x, r.y, r.z)[0]

            # inside should be mostly negative
            inside = [
                mc_near(t) for t in (gap.start_s + DELTA, 0.5 * (gap.start_s + gap.end_s), gap.end_s - DELTA)
            ]
            if sum(1 for v in inside if v < 0) < 2:
                fail(f"inside not mostly negative {pid} gap {gap.start_s:.2f}-{gap.end_s:.2f} {inside}")
            # outside neighbors (unless adjacent gap)
            for t, side in ((gap.start_s - DELTA, "before"), (gap.end_s + DELTA, "after")):
                # check if inside another gap of same sortie
                other = gdf[gdf.sortie_id == gap.sortie_id]
                in_other = (
                    (other.start_s <= t)
                    & (other.end_s >= t)
                    & ~((other.start_s == gap.start_s) & (other.end_s == gap.end_s))
                ).any()
                if in_other:
                    continue
                v = mc_near(t)
                # allow small negative within boundary tolerance band
                if v < -3.0:
                    fail(f"{side} of gap still deeply negative {pid} t={t} mc={v}")
    print("E41_GAPS_VALID")


if __name__ == "__main__":
    main()
