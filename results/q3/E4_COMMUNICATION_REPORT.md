# E4 Communication Report (E4.1)

## Gate

```text
E4_Q3_COMMUNICATION_READY
```

Validated: `E4_LINK_BUDGET_VALID`, `E4_LOS_VALID`, `E41_GAPS_VALID`, `E4_REPORT_CONSISTENT`.

## Link budgets (unchanged)

| pair | L_max |
| --- | ---: |
| transport ↔ G01 | 122.0 dB |
| transport ↔ relay | 116.0 dB |
| relay ↔ G01 | 126.0 dB |

## Methods (E4.1 corrections)

- analysis **per sortie_id only** (no cross-sortie interpolation)
- activity **takeoff_s … return_s** only (no prep)
- full `handover_start → handover_end` intervals
- adaptive sampling + **binary refine** of `M_C` sign / LOS transitions (0.1 s)
- gaps = maximal `{t: M_C<0}` with duration > 0.1 s

## Communication burden (auto CSV `q2_pareto_communication_burden.csv`)

| | P01 | P02 | P03 |
| --- | ---: | ---: | ---: |
| J_late | 28569.8 | **27140.2** | **27140.2** |
| J_norm | 0.5270 | 0.5257 | **0.5240** |
| sorties | 28 | 28 | 28 |
| active_time (s) | 37078.8 | 37072.8 | 37072.8 |
| gap_time (s) | 13378 | 13368 | 13372 |
| availability ratio | 0.639 | 0.639 | 0.639 |
| gap_count | 26 | 26 | 26 |
| max_gap (s) | 1143.5 | 1143.5 | 1143.5 |
| sorties requiring relay | 21 | 21 | 21 |
| min M_C (dB) | -6.2 | -6.2 | -6.2 |
| terrain gap (s) | 13370 | 13360 | 13364 |
| distance gap (s) | 0 | 0 | 0 |

Identity `active ≈ gap + available` holds (error ≈ 5e-10 s).

## Gap causes

Almost all gap time is **TERRAIN_BLOCKAGE**; distance-only gap time is **0** on all three plans.

## Which Q2 structure is easier to support?

Communication burden is **essentially tied** (gap_time 13368–13378 s). Slight edge to **P02** (lowest gap_time and lower `J_late` than P01). Differences are small versus terrain-induced gaps shared across plans.

## Need to change Q2 structure?

**Not strongly required for communication alone.** Prefer P02/P03 on timeliness; P01 is slightly worse on `J_late` with similar comm cost. Joint Q3 (relay energy) should re-rank.

## LOS disagreements

`results/q3/los_disagreements.csv` — 6 / 1000 pairs (99.4% agreement), near-tangent / cell-boundary class.

## Artifacts

- `results/q2/pareto_schedules/P01..P03/` (full traces)
- `results/q3/direct_margin_Pxx.csv`, `direct_gaps_Pxx.csv`, `direct_gaps.csv`
- `results/q3/q2_pareto_communication_burden.csv`
- `results/q3/los_disagreements.csv`

## Not done (by design)

Relay grid/placement, relay task merge, R01/R02, relay energy, Q3 ALNS, SOCP, ns-3 formal, Q4, E5.
