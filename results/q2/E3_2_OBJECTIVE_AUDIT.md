# E3.2 Objective Semantics Audit

## Decision

**E3_2_OBJECTIVE_SEMANTICS_READY**  
**E32_PARETO_SCHEDULES_VALID** (after package checks)

## 1. Why `J_late` is primary

Expected delivery time `D_b` is a **promise**; excess `t_b − D_b` is weighted overdue:

```text
J_late = Σ_b w_b · max(0, t_b − D_b_expected)
```

This matches “timeliness as deadline-related quality” and does not reward lateness that is still before `D_b` beyond a smooth score. Unit: priority-weighted seconds.

## 2. Why `J_norm` is kept

`J_norm = Σ w_b (t_b/D_b)/Σ w_b` remains a **secondary earlier-is-better** score when `J_late` ties (including both zero). Name: `weighted_normalized_delivery_time`. Not combined into one fixed scalar with `J_late`.

## 3. Did old Pareto change?

**Yes.** Reaudit (`e32_existing_solution_reaudit.csv`) under `(J_late, J_norm)` yields a different nondominated set vs the old `J_time`-first Pareto (e.g. old 26-sortie point has large `J_late`). Stage1+Stage2 were re-run.

## 4–5. Final true Pareto (K=3)

| id | J_late | J_norm | makespan | energy | sorties |
| --- | ---: | ---: | ---: | ---: | ---: |
| P01 | 28569.80 | 0.52701 | 10250.3 | 73.471 | 28 |
| P02 | 27140.24 | 0.52571 | 10326.9 | 73.350 | 28 |
| P03 | 27140.24 | 0.52404 | 10326.9 | 73.367 | 28 |

## 6. Zero-late?

**No.** `J_late_best_known = 28569.80 > 0`. All reported solutions have positive overdue.

## 7. ε budget type

`J_late` budget: `J_late ≤ (1+ε)·J_late_best_known` with `J_late_best_known = 28569.80` (from Stage1 min; Stage2 then found 27140.24 within ε=0 of that bound).

ε grid `{0, 0.01, 0.02, 0.05}` × `{makespan, energy, sorties}`. Full structures saved under `results/q2/epsilon_schedules/`.

## Artifacts

- `results/q2/e32_existing_solution_reaudit.csv`
- `results/q2/alns_runs_e32.csv`
- `results/q2/q2_pareto_e32.csv`
- `results/q2/pareto_schedules/P01..P03/`
- `results/q2/epsilon_schedules/`
