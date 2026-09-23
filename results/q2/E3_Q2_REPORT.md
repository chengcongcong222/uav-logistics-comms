# E3 Q2 Report

## Gate

**E3_Q2_TRANSPORT_READY**

Independent validator: `E3_Q2_VALID` (`validation/mathematical/e3_validate_q2.py`).

## Problem semantics

See `docs/model/Q2_SEMANTICS.md` (frozen). Hard deadlines are feasibility-only; timeliness uses continuous `J_time = Σ w_b (t_b/D_b)/Σ w_b`.

## Candidate missions

- `src/q2/mission.py` — Mission object (reuse for Q3)
- Multi-stop energy is **per-leg** with decreasing payload (no average-payload shortcut)
- Geometry: `data/processed/route_geometry.csv` (frozen)

## Physical gates T1–T5

| gate | role |
| --- | --- |
| T1 | box uniqueness / service consistency |
| T2 | mass |
| T3 | volume |
| T4 | energy + return reserve |
| T5 | relative hard-deadline reachability |

Stats: `results/q2/candidate_gate_stats.csv`, `candidate_gate_totals.csv` (contraction_ratio recorded).

## Resource decoder

`src/q2/scheduler.py` — deterministic UAV + battery assignment. ALNS does **not** encode UAV/battery/times.

- UAV busy: prep_start → return
- Battery: must be 100% at takeoff; cycle takeoff → return → recharge
- Prep/load may overlap prior charge (`MODEL_DERIVED`)
- Tie-break: earliest finish → earlier battery recovery → ID order

## Baselines vs Proposed

| method | J_time | makespan (s) | energy (kWh) | sorties |
| --- | ---: | ---: | ---: | ---: |
| B0 single-service | 0.5121 | 10550.9 | 85.63 | 32 |
| B1 greedy merge | 0.5440 | 9856.5 | 75.82 | 29 |
| **ALNS best** | **0.4701** | **8739.6** | **74.40** | **27** |

ALNS improves J_time, makespan, energy, and sorties vs both baselines (not a failure case).

## ALNS parameters

- Destroy: random_box, worst_timeliness, related_service, whole_mission, route_segment
- Repair: best_feasible_insertion, regret_2, hard_deadline_first
- Local: service_2opt, mission_split, uav_type_change (mission_merge used in B1)
- SA acceptance; seeds `2026092301`–`2026092310`
- Internal score tuple documented in code; report uses raw J1–J4

## Pareto / epsilon

`results/q2/q2_pareto.csv` — representatives under `J1 ≤ (1+ε)J1*` for ε ∈ {0,1%,2%,5%}. No single ε declared optimal.

## Final representative (ALNS best seed 2026092302)

- J_time **0.4701**
- makespan **8739.6 s**
- energy **74.403 kWh**
- sorties **27**
- hard deadline violations **0**
- resource conflicts **0**
- soft_late_count 6 (soft metric only)

## 10-seed stability

See `results/q2/stability_summary.json` and `alns_runs.csv`:

- best J_time ≈ 0.470, median ≈ 0.528, std modest across seeds
- sorties mostly 27–29
- runtime mean recorded per seed (≈15–70 s)

## Outputs

- `results/q2/q2_sorties.csv`, `q2_box_delivery.csv`, `q2_uav_calendar.csv`, `q2_battery_calendar.csv`
- `q2_objectives.csv`, `q2_pareto.csv`, `alns_runs.csv`, `operator_stats.csv`
- `candidate_gate_stats.csv`
- `Q2_submission.xlsx` (official mapping, does not modify raw template)
- `export/q2_transport_trace.csv` (mode/task_id/relay_id empty for Q3)

## Known limitations

1. B1 merge is heuristic and can worsen J_time while reducing sorties (tradeoff retained).
2. ALNS iterations modest for runtime; more iterations may improve J_time further.
3. Soft lateness still occurs on non-hard boxes (expected under capacity limits).
4. Climb energy remains `MODEL_ASSUMPTION_ACCEPTED` (frozen in E2.1).
