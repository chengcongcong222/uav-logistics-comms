"""Safety margins and SOC limits."""
from __future__ import annotations

DEFAULT_RHO = 0.20
RHO_GRID = [0.10, 0.15, 0.20, 0.25, 0.30]


def usable_energy_after_reserve(e_battery_kwh: float, rho: float) -> float:
    return (1.0 - rho) * e_battery_kwh


def end_soc_floor(rho: float) -> float:
    """Return reserve maps to SOC floor = rho (fraction)."""
    return rho
