# ARCHITECTURE_FREEZE_V1_1

Frozen mainline architecture (design only; ALNS/SOCP/Q2–Q4 not implemented yet).

## Pipelines

```text
Q1
Transport capacity boundary → single-service exact batching

Q2
Transport candidate missions
→ layered shrink (mass/volume/energy/deadline/dominance)
→ transport UAV + battery dual-resource scheduling
→ ALNS only as discrete searcher

Q3
Transport space-time trajectory
→ communication margin M_C(t)
→ continuous communication gaps
→ atomic relay mission generation
→ relay candidate-space shrink
→ communication-margin optimization
→ SOCP only as local refiner when beneficial
→ relay UAV + energy-component dual-resource scheduling
→ three-level least-disturbance feedback

Q4
Transport–relay mission dependency hypergraph
→ unsplittable mission blocks
→ K=2/3 exact partition
→ independent resource demand accounting

Validation
math validation → ns-3 packet-level validation → disturbance robustness validation
```

## Explicit exclusions

```text
RL = excluded
Lyapunov = excluded
Artificial potential field = excluded
New MAC protocol = excluded
Relay-relay multihop = prohibited
AODV/OLSR replacing relay schedule = prohibited
```
