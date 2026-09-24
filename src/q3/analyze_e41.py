"""E4.1 analyze: per-sortie gaps for all Pxx + LOS disagreements + report data."""
from __future__ import annotations

import random
from pathlib import Path

import pandas as pd

from src.common.paths import RESULTS_DIR, RESULTS_Q2
from src.common.terrain import Dem
from src.q3.gap_e41 import analyze_pareto_plan
from src.q3.link_budget import load_comm_params, pair_lmax
from src.q3.terrain_los import blocked_dense_sample, blocked_line_cells
from src.q3.trajectory import g01_position

RESULTS_Q3 = RESULTS_DIR / "q3"
PAR_DIR = RESULTS_Q2 / "pareto_schedules"


def los_disagreements(dem, n=1000, seed=20260923):
    rng = random.Random(seed)
    b = dem.bounds
    rows = []
    for _ in range(n):
        x1 = rng.uniform(b.left, b.right)
        x2 = rng.uniform(b.left, b.right)
        y1 = rng.uniform(b.bottom, b.top)
        y2 = rng.uniform(b.bottom, b.top)
        z1 = dem.sample(x1, y1) + rng.uniform(30, 400)
        z2 = dem.sample(x2, y2) + rng.uniform(30, 400)
        a = blocked_line_cells(dem, x1, y1, z1, x2, y2, z2)
        c = blocked_dense_sample(dem, x1, y1, z1, x2, y2, z2, 10.0)
        if a != c:
            rows.append(
                {
                    "endpoint_A": f"({x1:.6f},{y1:.6f},{z1:.2f})",
                    "endpoint_B": f"({x2:.6f},{y2:.6f},{z2:.2f})",
                    "primary_result": a,
                    "dense_result": c,
                    "min_clearance_m": None,
                }
            )
    pd.DataFrame(rows).to_csv(RESULTS_Q3 / "los_disagreements.csv", index=False)
    return n - len(rows), len(rows)


def main() -> None:
    RESULTS_Q3.mkdir(parents=True, exist_ok=True)
    params, _ = load_comm_params()
    l_max = pair_lmax()["transport<->G01"]
    dem = Dem()
    g01 = g01_position()
    from pyproj import Transformer
    from src.common.schemas import EPSG_UTM49N, EPSG_WGS84

    tf = Transformer.from_crs(EPSG_UTM49N, EPSG_WGS84, always_xy=True)
    glon, glat = tf.transform(g01[0], g01[1])
    g_ll = (glon, glat, g01[2])

    agree, disag = los_disagreements(dem)
    print(f"LOS agree={agree} disagree={disag}", flush=True)

    burdens = []
    all_gaps = []
    for pdir in sorted(PAR_DIR.glob("P*")):
        pid = pdir.name
        tr = pd.read_csv(pdir / "transport_trace.csv")
        meta = {}
        if (pdir / "metadata.json").exists():
            import json

            meta = json.loads((pdir / "metadata.json").read_text(encoding="utf-8"))
        print("analyze", pid, flush=True)
        mdf, gdf, burden = analyze_pareto_plan(pid, tr, dem, g01, g_ll, params, l_max)
        mdf.to_csv(RESULTS_Q3 / f"direct_margin_{pid}.csv", index=False)
        gdf.to_csv(RESULTS_Q3 / f"direct_gaps_{pid}.csv", index=False)
        if len(gdf):
            all_gaps.append(gdf)
        burden["J_late"] = meta.get("J_late")
        burden["J_norm"] = meta.get("J_norm")
        burden["transport_sorties"] = int(tr.task_id.nunique())
        # identity checks
        ident = abs(burden["active_time_s"] - (burden["direct_gap_time_s"] + burden["direct_available_time_s"]))
        burden["identity_error_s"] = ident
        if ident > 0.2:
            raise RuntimeError(f"burden identity fail {pid} err={ident}")
        burdens.append(burden)

    pd.DataFrame(burdens).to_csv(RESULTS_Q3 / "q2_pareto_communication_burden.csv", index=False)
    if all_gaps:
        pd.concat(all_gaps, ignore_index=True).to_csv(RESULTS_Q3 / "direct_gaps.csv", index=False)
    else:
        pd.DataFrame().to_csv(RESULTS_Q3 / "direct_gaps.csv", index=False)
    print("E41_ANALYZE_DONE", flush=True)


if __name__ == "__main__":
    main()
