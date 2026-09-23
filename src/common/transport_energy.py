"""Transport energy model.

See docs/model/FORMULA_AUDIT.md:
- E = E_hor + E_up  (structure SOURCE_GIVEN)
- E_hor = (d / L_g(q)) * E_use  (SOURCE_DERIVED from equivalent range)
- E_up  = eta_up * m * g0 * h+ / 3.6e6  (ASSUMPTION_REQUIRED)
- E_down = 0 when descent efficiency is 0 (SOURCE_GIVEN qualitative)
"""
from __future__ import annotations

G0 = 9.80665  # m/s^2
KWH_FROM_JOULE = 3.6e6


def equivalent_range_m(q_kg: float, range_empty_m: float, range_full_m: float, q_max_kg: float) -> float:
    """L_g(q) = L0 - (L0 - Lf) * (q/Q)^{3/2}  (SOURCE_GIVEN)."""
    if q_max_kg <= 0:
        raise ValueError("q_max_kg must be positive")
    q = max(0.0, min(float(q_kg), float(q_max_kg)))
    return range_empty_m - (range_empty_m - range_full_m) * (q / q_max_kg) ** 1.5


def horizontal_energy_kwh(distance_m: float, q_kg: float, range_empty_m: float, range_full_m: float, q_max_kg: float, e_use_kwh: float) -> float:
    """SOURCE_DERIVED: (d / L_g(q)) * E_use."""
    lg = equivalent_range_m(q_kg, range_empty_m, range_full_m, q_max_kg)
    if lg <= 0:
        raise ValueError("equivalent range must be positive")
    return (distance_m / lg) * e_use_kwh


def climb_energy_kwh(climb_m: float, mass_kg: float, climb_eff: float) -> float:
    """ASSUMPTION_REQUIRED: eta * m * g0 * h / 3.6e6."""
    return climb_eff * mass_kg * G0 * climb_m / KWH_FROM_JOULE


def descent_energy_kwh(descent_m: float, mass_kg: float, descent_eff: float) -> float:
    """SOURCE_GIVEN qualitative: descent_eff=0 => 0. Else same shape as climb (assumption)."""
    if descent_eff == 0.0:
        return 0.0
    return descent_eff * mass_kg * G0 * descent_m / KWH_FROM_JOULE


def leg_energy_kwh(
    distance_m: float,
    climb_m: float,
    descent_m: float,
    q_kg: float,
    empty_mass_kg: float,
    range_empty_m: float,
    range_full_m: float,
    q_max_kg: float,
    e_use_kwh: float,
    climb_eff: float,
    descent_eff: float,
) -> float:
    mass = empty_mass_kg + q_kg
    e_hor = horizontal_energy_kwh(distance_m, q_kg, range_empty_m, range_full_m, q_max_kg, e_use_kwh)
    e_up = climb_energy_kwh(climb_m, mass, climb_eff)
    e_dn = descent_energy_kwh(descent_m, mass, descent_eff)
    return e_hor + e_up + e_dn


def return_reserve_ok(energy_kwh: float, e_use_kwh: float, rho: float) -> bool:
    """SOURCE_GIVEN: E <= (1-rho)*E_use."""
    return energy_kwh <= (1.0 - rho) * e_use_kwh + 1e-12
