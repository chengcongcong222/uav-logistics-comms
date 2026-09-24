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

## Candidate contraction

Hierarchical 120→60→30 m × heights 50–300 m, gates R1–R7. Raw/after-stage counts in `relay_candidate_gate_stats_raw.csv`. Final feasible pairs in `relay_task_candidates.csv`.

## Candidate counts (tasks with sites)

- median ≈ 9–12, max 12 (search sample cap)
- tight tasks (`≤3` sites) present; bottlenecks = 8 unresolved intervals

## Timing

`as_is_timing_feasible` / `required_transport_shift_s` recorded; sites **not rejected** for timing (Q3 may shift transport).

## Relay-energy optimistic LB

Sum of per-task minimum `total_energy_kwh` (not final Q3 energy). Computed in `e5_stats.py` output / `relay_task_candidates.csv`.

## GRID_UNRESOLVED

**YES (8)** — time windows in `relay_unresolved.csv`. Labeled **grid-unresolved**, not physically impossible.

## Artifacts

`relay_sites.csv`, `relay_task_candidates.csv`, `relay_coverage_matrix.csv`, `relay_task_summary.csv`, `docs/model/Q3_RELAY_SEMANTICS.md`.

## Not done

R01/R02, energy packs, merge, transport shift, Q3 ALNS, SOCP, Γ_C, ns-3, Q4.
