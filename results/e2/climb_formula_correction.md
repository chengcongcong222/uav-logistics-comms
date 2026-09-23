# Climb Formula Correction (E2.1)

## Change

| item | old (`η·mgh/3.6e6`) | new (`mgh/(η·3.6e6)`) |
| --- | --- | --- |
| formula meaning | multiply by efficiency | divide by efficiency |
| `η=0.72` effect | underestimates battery energy | physically consistent with conversion efficiency |

Also: `E_down` is strictly 0 (all table efficiencies 0); non-zero descent efficiency raises and is not extrapolated. Climb requires `0 < η_up ≤ 1` when `h+ > 0`.

## Independent recompute vs repo outputs (ρ=20% unless noted)

Reference values from external cross-check (not hardcoded targets).

| metric | old repo | new repo | external ref (old→new) |
| --- | ---: | ---: | ---: |
| A max safe payload (all services) | 25.00 kg | **25.00 kg** | 25.00 → 25.00 |
| B hardest (S008) | 29.563 kg | **28.801 kg** | 29.56 → ~28.80 |
| C hardest (S008) | 60.283 kg | **58.904 kg** | 60.28 → ~58.9 |
| C–S004 | ~65.2 kg | **63.698 kg** | ~65.2 → ~63.7 |
| C–S003 | ~70.3 kg | **68.333 kg** | ~70.3 → ~68.2 |
| ρ=20% flights | 18 | **18** | 18 → 18 |
| ρ=20% total energy | 57.888 kWh | **59.107 kWh** | 57.89 → ~59.1 |
| ρ=20% total time | 32715.6 s | **32715.6 s** | (unchanged structure) |
| flights @ ρ=10/15/20/25/30% | 18/18/18/19/20 | **18/18/18/19/20** | same discrete jumps |

Energy increase: `(59.107 − 57.888) / 57.888 ≈ 2.11%`.

## Sensitivity flights (new)

| ρ | flights | total energy (kWh) | total time (s) |
| --- | ---: | ---: | ---: |
| 10% | 18 | 59.107 | 32715.6 |
| 15% | 18 | 59.107 | 32715.6 |
| **20%** | **18** | **59.107** | **32715.6** |
| 25% | 19 | 61.049 | 34505.2 |
| 30% | 20 | 67.203 | 36522.3 |

## Validation after correction

- `e2_validate_physics.py` → `E2_PHYSICS_OK` (includes new climb formula + eta bounds + descent strictness)
- `e2_validate_q1.py` → `E2_Q1_OK`
- `python -m src.q1.solve_q1` → 18 flights, 59.1066 kWh

Log: `results/e2/e21_rerun.log`

## Conclusion

Structural Q1 solution unchanged (18 flights); energy scale corrected ≈ +2.1%. Repo numbers are authoritative; external refs used only as sanity checks.
