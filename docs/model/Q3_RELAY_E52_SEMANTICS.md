# E5.2 relay candidate semantics

This stage supersedes E5/E5.1 **candidate generation and validation**, not the
frozen physical model. E5 tables remain historical warm starts. Their candidate
counts, margins and retention ratios are not E52 certificates.

## Scope

`generation_mode = LAZY_FEASIBILITY_FIRST`; `candidate_set_complete = false`.
Each final atomic task retains 1–3 independently validated candidate sites.
Finding a site is an existence result. It does not establish optimality,
enumerate the feasible region, or establish resource-feasible relay scheduling.
E6 may request targeted candidate expansion. No E6 scheduling runs in E52.

Old unresolved intervals are partitioned at phase boundaries and then into
pieces no longer than 30 seconds. Known sites are tested first, followed by
120/60/30 m grids when needed. Search uses necessary geometric tests, sparse
communication checks, and finally dense checks. Successful search stops early.
Budget expiry means unfinished search, never physical infeasibility.

The pairwise diameter test uses phase vertices of the piecewise-linear path.
It is a cheap finite calculation, not literally a zero-cost test. The corrected
bbox intersects the necessary T–R constraints for **all** phase vertices with
the R–G necessary range. DEM legality is checked on each proposed site.

## Trajectory and communication

- Reconstruct from `results/q2/pareto_schedules/Pxx/transport_trace.csv`.
- Identity is `(pareto_id, sortie_id)`; never interpolate between aircraft.
- Position interpolation uses bracketing phase points from the complete sortie,
  not only records lying inside a clipped gap.
- Check interval start/end, every phase/handover boundary, and a global 0.5 s
  lattice; refine observed LOS transitions to intervals no longer than 0.1 s.
- A negative sampled access margin rejects a candidate immediately. Both access
  and backhaul must satisfy the original zero-dB feasibility threshold.
- This is a **numerical whole-interval validation**, not a mathematical proof
  that arbitrarily short sub-grid outages cannot exist. A separate 0.25 s audit
  evaluates temporal sampling sensitivity without changing the physical model.
- The frozen primary DEM LOS routine remains authoritative. No new propagation
  model, obstruction attenuation, routing protocol or multihop is introduced.

## Energy, timing, identity, and merge-back

Cache site-specific backhaul and round-trip geometry/flight energy. Recompute
setup and service energy with the actual task duration. The independent
validator rebuilds terrain geometry, time, energy and SOC rather than trusting
stored energy summands.

Store required transport shift when preparation + outbound flight + setup
cannot meet a service start. Do not discard such sites or apply shifts in E52.

Site identity hashes exact floating-point `(x,y,AGL)` values; it does not merge
different locations by rounding to integer metres. Access cache identity
includes the site, plan, sortie and exact sample time. Static site data persist
in checkpoints; access samples are an in-memory cache and are regenerated for
unfinished tasks after restart.

After rescue, test adjacent task candidate unions for communication and energy
over the combined interval. Merge until no further adjacent merge succeeds
within those unions. This is not a proof of global minimum task count. If a
parent becomes one task, however, its task count cannot be reduced further.

The sum of per-task minimum retained-candidate separate-sortie energies is
**not a proven lower bound** for E6: merging distinct tasks may save repeated
travel/setup energy, while incomplete candidate pools may miss cheaper sites.
It is reported only as `separate_mission_min_energy_sum_kwh`.

## Persistence and metrics

Checkpoint after every completed/split atom and every parent merge. Resume
requires matching code, relevant data/DEM hashes, and configuration. Outputs
have `_e52` suffixes and are written via temporary files followed by replacement;
legacy result files are never cleared by the E52 runner.

Counts describe actually attempted computations, not the volume of the full
feasible domain. `cheap_candidates_examined` counts candidate/interval attempts,
including repeats. LOS calls are actual cache misses; cache hits are recorded
separately. Old exhaustive-run call counts were not captured, so an exact
before/after speedup or LOS-reduction factor cannot be claimed.

## Authoritative outputs and gate

- `results/q3/relay_atomic_tasks_e52.csv`
- `results/q3/relay_task_candidates_e52.csv`
- `results/q3/relay_sites_e52.csv`
- `results/q3/relay_unresolved_e52.csv`
- `results/q3/e52_run_meta.json`: search result; deliberately not a validator.
- `results/q3/e52_rescue/validation.json`: independent gate and artifact hashes.

Only zero unresolved intervals, every parent covered without holes/overlaps,
every task having candidates, and all retained pairs independently passing
communication/energy checks permit `E5_Q3_RELAY_TASKS_READY`.
