# Q3 E7 joint optimization semantics

The authoritative outputs are [the independently validated Pareto table](../../results/q3/e7/pareto_solutions.csv), its complete `solutions/Q3E7_001..008/` execution packages and [the artifact-bound gate](../../results/q3/e7/validation.json). E6 inputs remain immutable.

## Objectives and dominance

TimelinessKey is the lexicographic pair `(J_late, J_norm)`. This pair, joint makespan, total transport-plus-relay energy, transport sortie count and relay sortie count are the official dominance dimensions. No fixed weighted sum defines final optimality. Transport advances/delays and communication/energy margins are diagnostics only.

The epsilon family uses `J_late <= (1+epsilon) * best_known_J_late` for epsilon 0%, 1%, 2%, 5%, 10%, separately targeting makespan, energy and relay sorties. If the anchor lateness is zero, catalog selection instead budgets J_norm while requiring zero lateness. Archive selection uses the actual final best-known anchor. Repeated selected points at looser budgets indicate only the current archive's limits.

Numerical dominance tolerances are J_late 1e-4 weighted seconds, J_norm 1e-9, time 1e-6 seconds, energy 1e-8 kWh. The gate independently implements dominance and checks the final frontier against all search/control metric records. Only final points and the two reported execution controls receive complete independent E7 physical/full-flight audits; intermediate archive records are not all physically re-audited.

## L1 feasible space

Transport box-to-sortie assignment, service visit order and aircraft type are unchanged. Specific UAV/battery IDs, original resource order and all preparation/start times are free. Relative translations may be negative; absolute preparation times must remain nonnegative. A 40,000-second horizon bounds this search. Typed transport fleets and battery pools, hard medical/first-batch deadlines, capacities, reserve and charging requirements remain enforced.

Relay task grouping, fixed site, aircraft sequence and component allocation can change. The E6 two-relay/six-component calendar, one-to-many module-power accounting, paid idle hovering and no relay-to-relay rule remain in force. Each relay sortie uses exactly one hover point. No new bandwidth, MAC, throughput or robustness model is introduced.

Only L1 was activated. L2 equivalent missions and L3 local box regrouping were not required to achieve the measured substantial improvements; this does not prove those levels have no further benefit.

## Search and reproducibility limits

Continuous LP timing plus resource-capacity conflict repair is embedded in deterministic bounded relay-order/site/merge/split neighborhoods. The timing model uses a conservative continuously-active hover-span energy bound; final energy is recomputed from the actual active union and idle gaps. Energy proposal ranking uses that linear surrogate, whereas acceptance and dominance use exact frozen-model energy. Component capacity is checked by exact interval coloring after timing; rejected proposals do not prove mathematical infeasibility.

Deterministic evaluation budgets and library versions are recorded. The known frontier is neither exhaustive nor globally certified. Seventy existing sites were sufficient, so no full-DEM enumeration or new site generation was needed. Complete stored witnesses permit byte-identical execution-CSV replay without repeating search. Budget replay selects from the verified archive and independently validates the newly exported execution; it does not claim to solve a fresh global optimization problem.

## Communication authority

No new transport geometry was introduced in this L1 experiment. E6's two-second construction guards are retained only to construct assignments; complete shifted 3D flight trajectories and the frozen link model are the final authority. Every final point receives 0.5-second full-flight checking, explicit phase/task boundaries and observed LOS/sign changes refined to 0.1 seconds. The representative point receives an additional 0.25-second audit.

Gamma_C stays zero dB. Independent active-path margin quantiles and assignment-window minimum-margin quantiles are retained with explicit scopes. Zero observed uncovered duration is a numerical certificate, not an analytic continuous-time guarantee. No robustness Gamma_C scan, formal ns-3 campaign or Q4 work is part of E7.
