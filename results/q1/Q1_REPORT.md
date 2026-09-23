# Q1 Report

## Status

**E2_Q1_REVALIDATED** after E2.1 climb-energy correction (`mgh/η` instead of `η mgh`).

## Method

- Max safe payload: bisection on q with mass cap and `E_RT(q) ≤ (1-ρ)E_use`
- Outbound payload q, return 0
- Per-service exact set partition (min flights → min energy → min time); no ALNS; no cross-service
- Main case ρ = **20%**

## Key results (ρ=20%, corrected energy)

- Total flights: **18**
- Total transport energy: **59.1066 kWh** (was 57.8878 under old climb formula; +2.11%)
- Total cumulative operation time: **32715.6 s**
- All 80 boxes assigned exactly once

### Max safe payload (ρ=20%)

| type | min–max payload | hardest service | binding |
| --- | --- | --- | --- |
| A | 25.0–25.0 kg | all mass-capped | mass |
| B | 28.801–30.0 kg | S008 | energy |
| C | 58.904–80.0 kg | S008 | energy |

Artifacts: `results/q1/max_safe_payload.csv`, `results/q1/q1_packings_rho20.csv`

## Reserve sensitivity

| ρ | flights | energy (kWh) | time (s) |
| --- | ---: | ---: | ---: |
| 10% | 18 | 59.107 | 32716 |
| 15% | 18 | 59.107 | 32716 |
| **20%** | **18** | **59.107** | **32716** |
| 25% | 19 | 61.049 | 34505 |
| 30% | 20 | 67.203 | 36522 |

Discrete jumps remain 18→18→18→19→20.

## Validation

- `e2_validate_physics.py` → `E2_PHYSICS_OK`
- `e2_validate_q1.py` → `E2_Q1_OK`
- Comparison table: `results/e2/climb_formula_correction.md`
