"""Route geometry matrix builder + cross-check (two independent DEM max methods)."""
from __future__ import annotations

from itertools import product
from pathlib import Path

import pandas as pd

from src.common.paths import PROCESSED_DIR, RESULTS_E2
from src.common.route_geometry import climb_descent_m, planned_cruise_altitude_m
from src.common.schemas import ORIGIN_OPERATION_AGL_M, SERVICE_OPERATION_AGL_M
from src.common.terrain import Dem


def build_route_geometry() -> tuple[pd.DataFrame, pd.DataFrame]:
    nodes = pd.read_csv(PROCESSED_DIR / "nodes.csv")
    dem = Dem()
    by_id = {r.node_id: r for r in nodes.itertuples()}

    def op_alt(node_id: str) -> float:
        n = by_id[node_id]
        if n.node_type == "dispatch_center":
            return n.ground_elevation_m + ORIGIN_OPERATION_AGL_M
        return n.ground_elevation_m + SERVICE_OPERATION_AGL_M

    rows = []
    xrows = []
    for a, b in product(nodes["node_id"], nodes["node_id"]):
        if a == b:
            continue
        na, nb = by_id[a], by_id[b]
        d = float(((na.x_m - nb.x_m) ** 2 + (na.y_m - nb.y_m) ** 2) ** 0.5)
        max1 = dem.max_along_segment(na.longitude, na.latitude, nb.longitude, nb.latitude)
        max2 = dem.max_along_segment_cells(na.longitude, na.latitude, nb.longitude, nb.latitude)
        cruise = planned_cruise_altitude_m(max1)
        oa, ob = op_alt(a), op_alt(b)
        climb, descent = climb_descent_m(oa, ob, cruise)
        rows.append(
            {
                "from_id": a,
                "to_id": b,
                "horizontal_distance_m": d,
                "max_dem_elevation_m": max1,
                "planned_cruise_altitude_m": cruise,
                "origin_operation_altitude_m": oa,
                "destination_operation_altitude_m": ob,
                "climb_height_m": climb,
                "descent_height_m": descent,
            }
        )
        xrows.append(
            {
                "from_id": a,
                "to_id": b,
                "max_dem_dense_sample_m": max1,
                "max_dem_cell_walk_m": max2,
                "abs_diff_m": abs(max1 - max2),
            }
        )
    return pd.DataFrame(rows), pd.DataFrame(xrows)


def main() -> None:
    geom, xcheck = build_route_geometry()
    geom.to_csv(PROCESSED_DIR / "route_geometry.csv", index=False)
    xcheck.to_csv(RESULTS_E2 / "route_geometry_crosscheck.csv", index=False)
    print(f"legs={len(geom)} crosscheck_max_diff={xcheck['abs_diff_m'].max():.6f}")
    print("ROUTE_GEOMETRY_OK")


if __name__ == "__main__":
    main()
