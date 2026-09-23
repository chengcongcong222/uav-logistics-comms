# E3.1 Q2 Interface & Result Hardening Report

## Gate

```text
E3_1_Q2_HARDENED
E3_Q2_VALID
E3_TRACE_VALID
E3_PARETO_VALID
```

## 1. Transport trace interface (fixed)

`export/q2_transport_trace.csv` now has:

- continuous time from `preparation_start` to `return_s`
- per-leg `climb → cruise → descent` with explicit start/end markers
- **full handover interval** (`handover_start` / `handover_end`) matching
  `T = base + n_boxes * per_box`
- next climb begins at `handover_end`
- **return at O01** (x,y,z = O01 ground), time equals `return_s` (checked in generator)

Independent check: `validation/mathematical/e3_validate_trace.py` → **E3_TRACE_VALID**

## 2. Candidate gate metrics (fixed)

Was mis-labeled `contraction_ratio = accepted/generated`.

Now in `results/q2/candidate_gate_totals.csv`:

| metric | value |
| --- | ---: |
| generated | 2749 |
| accepted | 2482 |
| **retention_ratio** | **0.9029** |
| **rejection_ratio** | **0.0971** |
| failed_mass | 183 |
| failed_volume | 76 |
| failed_energy | 8 |
| failed_relative_deadline | 0 |

Correct wording: Q2 local-candidate physical gates reject **≈9.7%** (not “90% contraction”).  
Significant candidate-space shrink is deferred to **Q3 relay candidates**.

## 3. ε / Pareto logic (fixed)

- Stage1: 10 seeds × **80** iterations → `J_time_best_known = 0.478076` (min over seeds)
- Stage2: **true ε-constraint** subproblems for
  `ε ∈ {0,1%,2%,5%}` × `obj ∈ {makespan, energy, sorties}`
  with `J_time ≤ (1+ε)·J_time_best_known` enforced during search
- `results/q2/q2_epsilon_solutions.csv`
- `results/q2/q2_pareto.csv` = **true 4-objective nondominated set** (validated)

`validation/mathematical/e3_validate_pareto.py` → **E3_PARETO_VALID**

## 4. ALNS stability (80 iterations × 10 seeds)

See `results/q2/alns_runs.csv`, `stability_summary.json`:

- J_time best ≈ 0.478, median ≈ 0.512 (spread exists)
- sorties 26–29 across seeds
- honest statement: **存在一定随机波动，采用多随机种子并取非支配结果集**  
  (not “highly stable”)

## 5. Representative solution & true Pareto

`q2_pareto.csv` (4 nondominated points, `E3_PARETO_VALID`):

| source | J_time | makespan | energy | sorties |
| --- | ---: | ---: | ---: | ---: |
| stage1 seed 2302 | 0.4781 | **8739.6** | **72.96** | **26** |
| epsilon ε=0 | **0.4703** | 10597.4 | 79.95 | 30 |
| epsilon ε=0.01 | 0.4764 | 10410.6 | 77.36 | 29 |
| epsilon ε=0.01 | 0.4707 | 10597.4 | 78.98 | 29 |

Official dump uses lexicographic best J_time:

| | J_time | makespan | energy | sorties |
| --- | ---: | ---: | ---: | ---: |
| **REP (dumped)** | **0.4703** | 10597.4 | 79.95 | 30 |
| alt. (26 sorties) | 0.4781 | 8739.6 | 72.96 | 26 |
| B0 | 0.5121 | 10550.9 | 85.63 | 32 |
| B1 | 0.5440 | 9856.5 | 75.82 | 29 |

Both REP and the 26-sortie point are nondominated (tradeoff J_time vs makespan/energy/sorties).

Official files regenerated for REP: `q2_sorties.csv`, `q2_box_delivery.csv`, calendars, `Q2_submission.xlsx`, `q2_transport_trace.csv`.

## 6. Unchanged (frozen)

MODEL_FREEZE_V1, energy formulas, DEM geometry, deadline interpretation, battery semantics, J_time definition — **not modified**.

## Next gate

```text
E4_Q3_COMMUNICATION_MODEL
```
