# Q1 Report

## Status

**E2_Q1_OK** (exact packing, no ALNS)

## Method

- Max safe payload: bisection on q ∈ [0, Q_g] with mass cap and reserve constraint `E_RT(q) ≤ (1-ρ)E_use`
- Outbound payload q, return payload 0 (after drop)
- Batching: per service, no cross-service; exact set partition DP (min flights → min energy → min total time)
- Rho main case = **20%**

## Key results (ρ=20%)

- Total flights: **18**
- Total transport energy: **57.89 kWh**
- Total cumulative operation time: **32715.6 s**
- All 80 boxes assigned exactly once

### Max safe payload (ρ=20%)

| type | payload_limit (min–max) | dominant binding |
| --- | --- | --- |
| A | 25.0 kg (mass-capped) | mass |
| B | 29.56–30.0 kg | mostly mass |
| C | 60.28–80.0 kg | mixed mass/energy |

Artifacts: `results/q1/max_safe_payload.csv`, `results/q1/q1_packings_rho20.csv`

## Reserve sensitivity (`results/q1/reserve_sensitivity.csv`)

| ρ | flights | total energy (kWh) | total time (s) | energy-bound type×service count |
| --- | --- | --- | --- | --- |
| 10% | 18 | 57.89 | 32716 | 5 |
| 15% | 18 | 57.89 | 32716 | 5 |
| **20%** | **18** | **57.89** | **32716** | **6** |
| 25% | 19 | 59.78 | 34505 | 7 |
| 30% | 20 | 65.88 | 36522 | 14 |

Notes:

- Discrete flight-count jump at ρ=25% (18→19) and ρ=30% (→20)
- Farther/harder services switch from mass-bound to energy-bound as ρ rises
- C-type keeps higher payload headroom; A is mass-capped on all services at ρ≤20%

## Validation

`validation/mathematical/e2_validate_q1.py` → **E2_Q1_OK** (coverage, no cross-service, positive energy/time)

## Caveat

Energy model uses labeled assumptions from FORMULA_AUDIT; Q1 numbers must be re-checked after formula freeze.
