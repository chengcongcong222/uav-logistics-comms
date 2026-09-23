"""Load transport traces and G01 / relay positions."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.common.paths import EXPORT_DIR, PROCESSED_DIR, RESULTS_Q2, RESULTS_DIR
from src.common.schemas import SERVICE_OPERATION_AGL_M

RESULTS_Q3 = RESULTS_DIR / "q3"
PARETO_DIR = RESULTS_Q2 / "pareto_schedules"


def g01_position() -> tuple[float, float, float]:
    nodes = pd.read_csv(PROCESSED_DIR / "nodes.csv").set_index("node_id")
    n = nodes.loc["O01"]
    comm = pd.read_json(PROCESSED_DIR / "communication_parameters.json")
    # hG from json
    import json

    raw = json.loads((PROCESSED_DIR / "communication_parameters.json").read_text(encoding="utf-8"))
    h_g = float(raw["endpoints"]["固定网关 G01"]["天线离地高度（m）"]["value"])
    return (float(n.x_m), float(n.y_m), float(n.ground_elevation_m) + h_g)


def load_trace(path: Path | str) -> pd.DataFrame:
    return pd.read_csv(path)


def relay_position_legal(dem, lon: float, lat: float, agl_m: float) -> bool:
    if not (0.0 <= agl_m <= 300.0):
        return False
    try:
        dem.sample(lon, lat)
    except ValueError:
        return False
    return True
