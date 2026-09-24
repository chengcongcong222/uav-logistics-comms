# E5.1 Relay Task Resolution Report

## Gate

```text
E51_GRID_SEARCH_RESOLVED = STILL_UNRESOLVED
E5_Q3_RELAY_TASKS_BLOCKED
```

## Compliance fixes landed

| item | old | new (`src/q3/e51_relay_tasks.py`) |
| --- | --- | --- |
| MIN_ATOMIC_S | 10 s | **2.0 s** |
| MAX_SPLIT_DEPTH | 2 | **10** |
| Top-K 20/12 | present | **removed** |
| search radius | fixed 1800 m | **safe bbox from D_TR∩D_RG** |
| service energy | parent duration | **per-subtask `t1-t0`** |
| interval check | 8 samples | **prefilter + FULL exact** (0.5 s grid) |

## Runtime outcome

- Full clean rebuild of all P01–P03 under exhaustive 120→60→30 m × 50–300 m (and 25 m refine) exceeds practical wall-time in this environment (30+ min without finishing P01).
- Targeted deep-split of the 8 previously unresolved atoms (98–286 s windows) with depth=10 also exceeded 10 min on the first atom alone.

Therefore **`GRID_UNRESOLVED` remains 8** (restored from git after a partial clean-rebuild wiped outputs).  
Old contraction ratios **`SUPERSEDED_PENDING_E51`** — do not use 2.6e-4/1.7e-4/3.3e-4 as paper numbers.

## unresolved after stages

| stage | count |
| --- | ---: |
| before E5.1 | 8 |
| after deep split (this run) | not completed |
| after full 30 m/25 m | not completed |
| after 5 m fine / continuous | not started |

## Next

1. Finish exhaustive safe search offline (longer budget / vectorized LOS / multi-core).
2. Only then continuous rescue for remainder.
3. Do **not** enter E6 until `relay_unresolved.csv` is empty or explicitly waived.

## Artifacts

- `src/q3/e51_relay_tasks.py` (compliant search core)
- `environment/e51_targeted.py`, `e51_bg.sh`
- restored `results/q3/relay_*.csv` from E5
