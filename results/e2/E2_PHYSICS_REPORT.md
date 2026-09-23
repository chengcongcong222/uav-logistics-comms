# E2 Physics Report

## Status

**E2_1_PHYSICS_CORRECTED**  
**E2_PHYSICS_OK**  
**MODEL_FROZEN** (see `docs/model/MODEL_FREEZE_V1.md`)

## E2.1 correction

Climb energy changed from `η·m·g0·h/3.6e6` to:

```text
E_up = m · g0 · h+ / (η_up · 3.6e6)
```

with `0 < η_up ≤ 1` enforced when `h+ > 0`. Descent energy is strictly 0.

Evidence labels updated in `docs/model/FORMULA_AUDIT.md`:

- `E_hor` → `MODEL_DERIVED`
- `E_up` → `MODEL_ASSUMPTION_ACCEPTED`
- handover/load stacking → `MODEL_DERIVED`
- none of these claimed as `SOURCE_GIVEN`

## Modules

`terrain.py`, `route_geometry.py`, `flight_time.py`, `transport_energy.py`, `charging.py`, `margins.py`

## Tests

`validation/mathematical/e2_validate_physics.py` → `E2_PHYSICS_OK`  
(includes new climb formula identity, eta bounds, descent strictness)

## Route geometry

240 directed legs; DEM max cross-check max |Δ| ≈ 16.4 m (discretization only).

## Comparison / rerun log

- `results/e2/climb_formula_correction.md`
- `results/e2/e21_rerun.log`
