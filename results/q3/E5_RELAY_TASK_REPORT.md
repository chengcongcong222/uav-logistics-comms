# E5 Relay Task Report

## Gate

```text
E5_Q3_RELAY_TASKS_BLOCKED
```

Reason: **8 atomic intervals remain `GRID_UNRESOLVED`** after hierarchical spatial search + height refine + targeted rescue (`results/q3/relay_unresolved.csv`). Per spec this blocks E6 until continuous-position rescue.

Validators: `E5_RELAY_CANDIDATES_VALID`, `E5_RELAY_ENERGY_VALID`, `E5_ATOMIC_TASKS_VALID_WITH_GRID_UNRESOLVED n=8`.

## Gaps → atomic tasks

| plan | direct gaps | atomic tasks | full-gap 1-site | split gaps | GRID_UNRESOLVED |
| --- | ---: | ---: | ---: | ---: | ---: |
| P01 | 26 | 32 | 22 | 4 | 2 |
| P02 | 26 | 32 | 23 | 3 | 4 |
| P03 | 26 | 28 | 25 | 1 | 2 |

Most gaps are covered by **one fixed site**. Splits only when no common site covers the full gap.

## Candidate contraction (measured)

| plan | raw 3D samples | after T-R+R-G range | after backhaul | after endpoint | after full-interval | after energy | retention |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| P01 | 843069 | 1160 | 1054 | 1010 | 217 | 217 | 2.6e-4 |
| P02 | 1310547 | 700 | 623 | 583 | 225 | 225 | 1.7e-4 |
| P03 | 743827 | 740 | 651 | 600 | 248 | 248 | 3.3e-4 |

**rejection_ratio ≈ 99.97%+** — strong Q3 layered-contraction evidence.

Library: **592 sites**, **836 (task,site)** pairs.

## Candidate counts (tasks with sites)

- median 12 (cap), mean 8.6–9.4, min 1
- 8 tight tasks (`≤3` sites)

## Timing

All recorded feasible pairs: **zero_shift = all** (max required shift 0.0) for P01–P03 resolved tasks.

## Relay-energy optimistic LB (Σ min E per task)

| plan | E_LB (kWh) | tasks with sites |
| --- | ---: | ---: |
| P01 | 8.656 | 30 |
| P02 | 8.587 | 28 |
| P03 | 8.095 | 26 |

## GRID_UNRESOLVED

**YES (8)** — time windows in `relay_unresolved.csv`. Labeled **grid-unresolved**, not physically impossible.

## Artifacts

`relay_sites.csv`, `relay_task_candidates.csv`, `relay_coverage_matrix.csv`, `relay_task_summary.csv`, `docs/model/Q3_RELAY_SEMANTICS.md`.

## Not done

R01/R02, energy packs, merge, transport shift, Q3 ALNS, SOCP, Γ_C, ns-3, Q4.
