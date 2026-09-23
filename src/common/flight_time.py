"""Flight time model — SOURCE_GIVEN formula."""
from __future__ import annotations


def leg_flight_time_s(
    climb_m: float,
    distance_m: float,
    descent_m: float,
    v_climb_mps: float,
    v_cruise_mps: float,
    v_descend_mps: float,
) -> float:
    """t = h+/v↑ + d/vc + h-/v↓  (SOURCE_GIVEN)."""
    return climb_m / v_climb_mps + distance_m / v_cruise_mps + descent_m / v_descend_mps


def handover_time_s(n_boxes: int, base_s: float, per_box_s: float) -> float:
    """MODEL_DERIVED: base + n*per_box (field-name semantics)."""
    return base_s + n_boxes * per_box_s


def load_time_s(n_boxes: int, per_box_s: float) -> float:
    """MODEL_DERIVED: n*per_box."""
    return n_boxes * per_box_s
