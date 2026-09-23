# E2 Physics Report

## Status

**E2_PHYSICS_OK** (tests pass under labeled assumptions)  
**E2_FORMULA_STATUS = PARTIAL_WITH_GAPS** (see FORMULA_AUDIT.md)

## What was built

- `src/common/terrain.py` — DEM access
- `src/common/route_geometry.py` — leg geometry
- `src/common/flight_time.py` — SOURCE_GIVEN time model
- `src/common/transport_energy.py` — range/energy/reserve
- `src/common/charging.py` — SOURCE_GIVEN two-stage charge
- `src/common/margins.py` — reserve grid
- `data/processed/route_geometry.csv` — 240 directed legs
- `results/e2/route_geometry_crosscheck.csv` — dense sample vs cell-walk DEM max

## Route geometry

- Nodes: O01 + S001–S015
- Cruise alt = max DEM along leg + 50 m
- Cross-check |Δmax DEM| max ≈ 16.4 m (method discretization; not a data error)

## Unit tests (`e2_validate_physics.py` → `E2_PHYSICS_OK`)

- L(0)=L0, L(Q)=Lf, non-increasing in q
- Energy non-decreasing in q
- Return reserve inequality
- Charge endpoints + continuity at SOC=0.9
- Positive climb/cruise/descent time terms

## Assumptions used (must be confirmed)

1. `E_up = η_up · m · g0 · h+ / 3.6e6` (not printed in DOCX)
2. `E_hor = (d / L(q)) · E_use` (derived from equivalent range)
3. Handover = `base + n · per_box`
