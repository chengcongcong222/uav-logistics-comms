"""Flight geometry helpers (E2)."""
from __future__ import annotations

import numpy as np

from .schemas import CRUISE_MARGIN_ABOVE_MAX_DEM_M


def horizontal_distance_m(x1: float, y1: float, x2: float, y2: float) -> float:
    return float(np.hypot(x2 - x1, y2 - y1))


def planned_cruise_altitude_m(max_dem_along_leg_m: float) -> float:
    """SOURCE_GIVEN: max DEM ground elevation along leg + 50 m."""
    return float(max_dem_along_leg_m) + CRUISE_MARGIN_ABOVE_MAX_DEM_M


def climb_descent_m(
    origin_op_alt_m: float, dest_op_alt_m: float, cruise_alt_m: float
) -> tuple[float, float]:
    climb = max(0.0, cruise_alt_m - origin_op_alt_m)
    descent = max(0.0, cruise_alt_m - dest_op_alt_m)
    return float(climb), float(descent)
