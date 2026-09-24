# E8 robustness semantics and reproducibility

Gamma_C = 0, 2, 4, 6 dB is an additional physical link-margin requirement.
It applies to direct transport–gateway and both relay-path hops. The frozen
fading allowance is unchanged. Box groups, visit order, aircraft types, two
relay UAVs and six energy components are fixed. Only E7 L1 decisions change.

## Demand and candidates

A 0.5-second direct-margin profile includes phase vertices and observed LOS or
threshold crossings refined to 0.05 seconds. Deficient intervals receive a
two-second construction guard clipped to the flight. Positive direct physical
margin below Gamma still requires a relay. Candidate generation uses necessary
LOS geometry, targeted 120-m grids and 300/250/200-m altitudes. The set is not
complete. Internal slack is rebased above Gamma; exported dB margins are raw
physical values. No frozen link-budget file is changed.

Cached tasks are read without regeneration during replay. Changing the partition
config requires explicit demand and candidate rebuilding. For Gamma 6, long gaps
on M001–M008 are partitioned into equal subintervals of at most 300 seconds. The
guarded union is unchanged. A relay sortie still uses one fixed site. At a shared
endpoint the incoming interval supplies the provider; both access intervals are
validated including that endpoint. Positive-duration assignment overlap is
forbidden. No handover latency, new MAC or multihop model is added.

## Optimization and interpretation

E7 dominance and epsilon semantics remain fixed: lexicographic TimelinessKey
(J_late, J_norm), makespan, total energy, transport sorties and relay sorties.
Epsilon values are 0, .01, .02, .05, .1. Gamma 0 preserves the eight final E7
points exactly. Gamma 2 and 4 reuse the E7 generator after bounded MILP seed
construction. Common absolute lateness-budget comparisons are also provided.

The timing relaxation conservatively charges the full service span as active
hover. Accepted witness energy and independent audits charge exact active-window
unions and idle hover. Free typed-resource conflict repair and complete resource
calendars are required. Reported fronts are finite known archives, not global
fronts. True feasible sets shrink with Gamma; separately searched archives need
not be nested. Cost increments are achievable witness comparisons, not minimum
unavoidable robustness costs. Used component IDs do not prove minimum pool size.

## Gamma 6 status

No executable witness was found. Whole-gap regrouping, short-flight candidates,
35 early partitions, subinterval handover and joint site/assignment/time MILPs
were tried. The last models retain 28 coverage signatures and allow two or three
early sorties per relay. Candidate, signature, subdivision and sortie-count
restrictions preclude a physical infeasibility claim. The gate remains
E8-B remains GAMMA6_NO_WITNESS_FOUND after the user-authorized single final rescue. E8-A (0/2/4 dB) is DONE; the certified tested robustness level is 4 dB. User policy explicitly removes Gamma 6 as a Q4 gate. Q4 is independently completed from Gamma-zero Q3E7_001; ns-3 is optional/late.

## Audit and replay

All 23 retained points receive independent 0.5-second full-flight audits, with
observed boundaries refined to 0.1 seconds. One representative per feasible
scenario also passes 0.25-second checks. The validator does not import scheduler
feasibility or energy routines. It recomputes transportation physics, box-level
deadlines, typed resource calendars, relay energy and whole-flight coverage.
This numerical certificate is not an analytic continuous-time proof.

Run from the repository using .venv/bin/python and BLAS/OMP/MKL threads set to 1.
Module src.q3.e8_replay --check-all reconstructs CSVs from saved witnesses and
checks byte identity. The --gamma G --epsilon E --objective O --output DIR form
copies a hash-verified canonical selection to a new path. Copied historical
audits refer to the canonical source; rerun e8_validate.py on DIR to bind its
own audit paths.

To rerun from saved candidates use modules src.q3.e8_seed_variants 2,
src.q3.e8_pareto 2, src.q3.e8_audit_batch 2; similarly for Gamma 4. HiGHS seed
search is wall-clock limited and may produce a different incumbent. There is
no randomized seed. Persisted witnesses and CSV replay are the deterministic
reproducibility authority.

Candidate rebuilding is explicit: module src.q3.e8_candidates 2 (or 4).
Gamma 6 whole-gap evidence is preserved in whole_gap_diagnostics. To recreate
split demands, write the stored demand_config.json and call derive_demands(6)
before constructing RobustEngine(6), then check saved sites against all new
atomic intervals. Whole-gap edges cannot be reused by name. This exploratory
sequence is documented, not claimed as a guaranteed-success solver command.

After any search/export change, rerun independent audits, replay, gate, report,
then gate again to bind derived reports. Check hashes before using an old gate.
E8 does not change the authority of E6/E7. See Q4_PARTITION_SEMANTICS.md for the separately authorized and validated Q4 stage.
