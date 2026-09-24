# E5.2 — Lazy relay feasibility and independent audit

## Decision

```text
E52_FEASIBILITY_RESOLVED
E52_RELAY_CANDIDATES_VALID
E52_RELAY_ENERGY_VALID
E52_ATOMIC_TASKS_VALID
E52_QUARTER_SECOND_CHECK_VALID
E5_Q3_RELAY_TASKS_READY
```

**E6 has not started.** READY means a validated relay-site witness exists for
every atomic interval. It does not mean that two relay UAVs and six energy
components can already execute these intervals jointly.

`candidate_set_complete = false`; `generation_mode = LAZY_FEASIBILITY_FIRST`.
The authoritative gate is `e52_rescue/validation.json`, bound to artifact hashes.
The generator's `PENDING_INDEPENDENT_VALIDATION` field records its status before
the separate audit; it is not an additional unresolved scientific gate.

## Final canonical results

| Plan | Parent gaps | Atomic tasks | Candidate pairs | Sites within plan | Min two-hop margin/dB | Separate-mission min-energy sum/kWh |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| P01 | 26 | 26 | 43 | 37 | 0.213151 | 10.234907 |
| P02 | 26 | 26 | 43 | 37 | 0.026971 | 10.207950 |
| P03 | 26 | 26 | 40 | 34 | 0.026971 | 10.233602 |

- Global: **78 parent gaps, 78 atomic tasks, 126 candidate pairs, 68 unique sites,
  zero unresolved intervals**. Site counts overlap between plans.
- Every original gap now has a whole-gap fixed-site witness. No split gaps
  remain. Thus one task per gap is minimal within the fixed parent-gap setup;
  this does not optimize merging across different parents.
- Candidate counts: 48 tasks have one site, 12 have two, and 18 have three.
- All 78 tasks, and all 126 retained pairs, have zero individually required
  transport shift. This does not include fleet/resource conflicts.
- Minimum energy margin over all retained pairs:
  **1.885353 kWh**.
- Minimum two-hop margin is **0.026971 dB**;
  the tightest limit is the backhaul. Minimum access margin is
  **0.096180 dB**. These witnesses have no guaranteed
  additional 2/4/6 dB robustness budget.
- Energy sums in the table concern separate missions using retained candidates.
  They are **not a proven lower bound on E6 energy**: task merging can save
  repeated travel/setup, and lazy pools may omit lower-energy sites.

## What changed and why the old result was unreliable

1. Corrected necessary bbox intersection extrema, including in archived E5.1.
2. Removed cross-sortie interpolation from the active E52 path. Trajectories now
   come from canonical P01–P03 trace packages, keyed by plan and sortie, with
   bracketing phase points retained.
3. Use vectorized distance gates, cached static backhaul/geometry and identified
   access samples; verify dense intervals only after sparse checks pass.
4. Use old candidate/site tables only as warm starts. Generate separate `_e52`
   canonical tables; do not overwrite legacy tables or append unverified rows.
5. Preserve endpoints/phase/handover boundaries and use <=0.5 s sampling with
   observed LOS transition refinement <=0.1 s. Independent audit reconstructs
   every retained pair and energy from inputs, not stored energy summands.
6. Checkpoint after each atom/parent; bind resume to code/config/input hashes,
   including the DEM file. Static caches persist; access caches are in-memory.

The bbox correction alone should not receive all performance credit. On the 78
correctly isolated parent trajectories, old/new necessary-box area ratios range
from 1.053 to 2.463, median 1.258. This is not an ablation timing experiment.
Lazy existence search, corrected trajectory identity and cached computation all
contribute. No isolated causal speedup factor is claimed.

## Rescue provenance

The historical “8 unresolved parents” are actually **8 unresolved old atoms in
5 distinct parent gaps**.

| Event category before merge-back | Count |
| --- | ---: |
| Old resolved atoms presented for revalidation | 84 |
| Revalidated using selected old candidates (at most 3 tried) | 37 |
| Other old resolved atoms rescued using site library | 44 |
| Other old resolved atoms rescued by new 120 m grid | 3 |
| Old unresolved atoms | 8 |
| <=30 s pieces made from those 8 atoms | 42 |
| Those pieces rescued using existing library | 42 |
| Deeper split operations | 0 |
| 60/30 m grid rescue, local 5 m rescue, continuous rescue | 0 |
| Total successful search jobs before merge-back | 126 |
| Successful adjacent merge-back operations | 48 |

Failure of the selected three warm candidates does not prove an old task
infeasible. It demonstrates why old candidate tables cannot be accepted without
revalidation. The three new-grid rescues were P01 G000/A02, G003/A00 and G007/A00;
later plans could reuse these newly cached sites.

The 8 formerly unresolved atoms did not need exhaustive 30 m / 25 m search or
continuous optimization. The <=30 s split was a construction device; successful
merge-back eventually supplied a witness for each original full gap.

## Measured computation

| Metric | Measured value |
| --- | ---: |
| Cheap candidate/interval attempts, including repeat attempts | 94771 |
| After vectorized range gates | 62159 |
| Sparse interval checks | 2642 |
| Dense interval checks, including revalidation/merge-back | 253 |
| Actual T–R LOS calls | 120574 |
| Actual R–G LOS calls | 946 |
| Access cache hits / hit rate | 38371 / 24.14% |
| R–G cache hits / hit rate | 4020 / 80.95% |
| Static flight-geometry calculations | 73 |
| Static geometry cache hits | 180 |
| Generation + merge-back, resumed run | 19.743 s |
| Independent 0.5 s candidate/energy/coverage audit | 16.256 s |
| Additional all-pair 0.25 s audit | 30.286 s |

One worker; OMP/MKL/OpenBLAS thread limits = 1. Runtime excludes interpreter/
initial input loading and is not the full engineering-turn duration. Search
counts include provisional and merged candidates, not just final retained pairs.
Old exhaustive-run LOS counts and completed runtime do not exist; no numerical
before/after speedup ratio or complete feasible-site retention rate is reported.

## Validation and reproducibility evidence

- All 126 final pairs independently checked; 68 site legality/backhaul checks.
- Independent 0.5 s audit: 107676 access samples and
  66 transition refinement samples.
- Additional 0.25 s audit: **126 pairs, 0 violations**,
  214651 access samples. Maximum absolute access-minimum change versus
  the stored 0.5 s result: 1.21e-12 dB.
- All 78 E4 parent gaps covered exactly within numerical tolerance, without
  holes or overlaps, with positive duration and >=1 candidate per task.
- Final adjacent-union checks = 0 because every parent already has one task.
  Generation performed 48 verified merge-back operations.
- 10 targeted regressions passed: intersection/diameter necessity, no unsafe
  geometric exclusions, sortie isolation, phase endpoints, no extrapolation,
  dense/refined outage rejection, task-aware caches, energy-duration update,
  and scientific-input fingerprint coverage.
- Controlled stop after 3 jobs, followed by resume, completed all 126 jobs;
  changed-code stale checkpoint was explicitly rejected. Pilot and final
  canonical table hashes agree, despite the intervening persistence hardening.
- Raw-data and repository hygiene checks are rerun before publication. Existing
  unrelated Q2 working-tree changes and the missing legacy E5 gate-stat CSV
  remain untouched; only E52-related paths are committed.

Numerical sampling remains a finite-resolution test, **not an analytic proof of
continuous-time connectivity**. The primary frozen DEM LOS primitive is reused;
the independent validator independently reconstructs its inputs and propagation
arithmetic. The 0.25 s audit tests time-resolution sensitivity, not a different
terrain-occlusion model.

## Artifacts and reproduction

- `src/q3/e52_geometry.py`, `src/q3/e52_lazy.py`
- `validation/mathematical/e52_validate_candidates.py`
- `validation/mathematical/e52_sampling_sensitivity.py`
- `validation/mathematical/e52_test_regressions.py`
- `docs/model/Q3_RELAY_E52_SEMANTICS.md`
- `relay_atomic_tasks_e52.csv`, `relay_task_candidates_e52.csv`, `relay_sites_e52.csv`,
  `relay_unresolved_e52.csv`, `e52_run_meta.json`
- `e52_rescue/checkpoint.json`, `resolved_atoms.csv`, `candidate_sites.csv`,
  `progress_events.json`, independent audit CSVs, validation and sensitivity JSONs.

```bash
cd /home/ccc/projects/uav-logistics-comms
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
.venv/bin/python -m src.q3.e52_lazy --resume
.venv/bin/python validation/mathematical/e52_validate_candidates.py
.venv/bin/python validation/mathematical/e52_sampling_sensitivity.py
.venv/bin/python validation/mathematical/e52_test_regressions.py
.venv/bin/python environment/e52_report.py
```

On a fresh output directory omit `--resume`. Preserve the old checkpoint before
a clean rebuild; never bypass a fingerprint mismatch. Input data and the Python
environment are local dependencies and remain outside version control.

## Next handoff boundary

Stop at E5.2. E6 may consume the new tables to examine task overlap, shared-site
merging, two relay UAVs and six independently charged energy components. It must
not mistake zero per-task shift for fleet-feasible zero shift. With 48 singleton
candidate pools and narrow margins, targeted candidate expansion may be needed.

Do not rerun Q2 or modify its objective/physics merely to accommodate this
candidate generator. Use the canonical E3.2 P01–P03 packages; legacy top-level Q2
objectives and schedules were already inconsistent before this change.
