# E4 Communication Report

## Gate

```text
E4_PARETO_SCHEDULES_READY
E4_LINK_BUDGET_VALID
E4_LOS_VALID
E4_GAP_VALID
E4_Q3_COMMUNICATION_READY
```

## 1. Link budgets (from attachment parameters)

| pair | L_max |
| --- | ---: |
| transport ↔ G01 | **122.0 dB** |
| transport ↔ relay | **116.0 dB** |
| relay ↔ G01 | **126.0 dB** |

Theoretical ranges (code-computed): T-G 12.51 km LOS / 3.96 km +10 dB; T-R 6.27 / 1.98 km; R-G 19.83 / 6.27 km.

## 2. DEM occlusion

Two independent implementations (raster line vs dense ≤10 m). Cross-check 1000 random 3D pairs: **agreement 99.4%** (`E4_LOS_VALID`). Endpoint self-occlusion excluded.

## 3–6. Q2 Pareto communication burden (direct only)

| | P01 | P02 | P03 | P04 |
| --- | ---: | ---: | ---: | ---: |
| transport sorties | 26 | 28 | 29 | 30 |
| direct availability ratio | 0.857 | 0.843 | 0.854 | 0.859 |
| gap count | **100** | 106 | **87** | 101 |
| total gap duration (s) | **13418** | 15809 | 15444 | 15683 |
| max single gap (s) | 939 | 1017 | **794** | 824 |
| sorties needing relay | 26 | 28 | 27 | 30 |
| min M_C (dB) | -6.2 | -6.2 | -6.2 | -6.2 |
| terrain-caused gap (s) | 13418 | 15809 | 15444 | 15683 |
| distance-caused gap (s) | **0** | 0 | 0 | 0 |

**All gaps are terrain-caused** (not range). Distance-only duration is zero on all four plans.

## 7. Is one Q2 structure easier to support?

**P01 (26 sorties)** has the **lowest total communication gap burden** (13.4 ks vs 15.4–15.8 ks) and the fewest sorties requiring relay support coverage windows in aggregate time, despite P03 having fewer discrete gap segments.

P01 is also best on transport energy / makespan / sorties (E3.1). Evidence currently **favors P01** for joint Q3.

## 8. Need to change Q2 transport structure?

**Not yet required to redesign Q2**, but there is already evidence that the 26-sortie Pareto point is simultaneously better on transport metrics *and* lower direct-gap burden than the more “timely” 30-sortie point. Q3 should still re-optimize jointly (relay energy may change the ranking).

## Pareto schedule persistence

`results/q2/pareto_schedules/P01..P04/` with sorties, deliveries, calendars, `transport_trace.csv`, `objectives.json`, `missions.json`.

- **P01** exact match to stage1 seed `2026092302` metrics.
- **P02–P04** are real ALNS recoveries (saved mission structures). Exact original Stage2 epsilon points were not structure-cached; recovery used explicit seeds (`fast_eps_points.py`, `fix_p03.py`). Metrics recorded in each `objectives.json`. All traces pass `E3_TRACE_VALID` when regenerated.

## Artifacts

- `results/q3/link_budget.csv`, `theoretical_ranges.csv`
- `results/q3/direct_margin_Pxx.csv`, `direct_gaps_Pxx.csv`, `direct_gaps.csv`
- `results/q3/q2_pareto_communication_burden.csv`
- `docs/model/Q3_COMMUNICATION_SEMANTICS.md`
- Relay margin helpers in `src/q3/communication_margin.py` (no scheduling)

## Not done (by design)

Relay placement, R01/R02 assignment, relay energy packs, Q3 ALNS, SOCP, ns-3 formal runs, Q4.
