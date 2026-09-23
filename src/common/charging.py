"""Two-stage equivalent charging — SOURCE_GIVEN formula."""
from __future__ import annotations


def charge_time_s(soc: float, t_full_s: float) -> float:
    """t_chg(s) piecewise linear, SOC s in [0,1]."""
    s = float(soc)
    if s < 0.0 or s > 1.0:
        raise ValueError("soc must be in [0,1]")
    if s < 0.90:
        return t_full_s * (0.65 * (0.90 - s) / 0.90 + 0.35)
    return t_full_s * (0.35 * (1.0 - s) / 0.10)


def soc_after_energy(soc0: float, energy_used_kwh: float, e_use_kwh: float) -> float:
    return soc0 - energy_used_kwh / e_use_kwh
