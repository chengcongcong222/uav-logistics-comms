# UAV Logistics & Relay Communication Lab

UAV logistics trajectory planning and relay-communication validation workspace.
Python models produce standardized trajectories/schedules; ns-3.47 validates mobility + Wi-Fi + UDP + FlowMonitor.

Current stage: **E5.2 relay-candidate rescue**. Q1, Q2 and the reference
communication-gap model are implemented. See
[`results/q3/E52_REPORT.md`](results/q3/E52_REPORT.md) for the current gate,
results, validation evidence and limitations. E6 resource scheduling has not
started. The E0 instructions below describe the frozen environment, not current
implementation progress.

## Current result authority

- Q2: `results/q2/pareto_schedules/P01..P03/`, `q2_pareto_e32.csv` and
  `e32_summary.json`. Legacy top-level Q2 files are not a synchronized package.
- Q3 candidates: `relay_atomic_tasks_e52.csv`, `relay_task_candidates_e52.csv`,
  `relay_sites_e52.csv`, `relay_unresolved_e52.csv` under `results/q3/`.
- Gate: `results/q3/e52_rescue/validation.json`, bound to result SHA256 hashes.
- Candidate pools are **incomplete** feasibility witnesses, not exhaustive
  feasible-site sets or a resource-feasible Q3 schedule.
- Model details: [`Q3_RELAY_E52_SEMANTICS.md`](docs/model/Q3_RELAY_E52_SEMANTICS.md).

```bash
# Existing checkout with saved checkpoint; use --resume to avoid repeating work.
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
.venv/bin/python -m src.q3.e52_lazy --resume
.venv/bin/python validation/mathematical/e52_validate_candidates.py
.venv/bin/python validation/mathematical/e52_sampling_sensitivity.py
.venv/bin/python validation/mathematical/e52_test_regressions.py
```

On a fresh run without a checkpoint, omit `--resume`. A checkpoint whose
input/code/config hash differs is rejected; preserve it separately before a
clean rebuild. Do not use legacy `e51_relay_tasks` to regenerate E52 results.

## Stack (frozen)

```text
Windows 10/11
  └── WSL2
        └── Ubuntu 24.04 LTS
              ├── Python 3 + venv
              ├── NumPy / SciPy / pandas / openpyxl / matplotlib
              ├── rasterio / pyproj
              ├── CMake + Ninja + GCC/g++
              └── ns-3.47
```

## Layout

```text
uav-logistics-comms/
├── AGENTS.md
├── README.md
├── environment/          # env docs, versions, bootstrap scripts
├── data/
│   ├── raw/              # immutable source inputs
│   ├── processed/        # derived datasets
│   └── cache/            # computation cache
├── src/                  # Q1–Q4 model code (not in E0)
├── validation/
│   ├── mathematical/     # Python smoke
│   ├── ns3/              # ns-3 smoke
│   └── robustness/
├── export/               # Python → ns-3 CSV interface
├── experiments/
├── results/
│   ├── e0/
│   ├── q1/ … q4/
│   └── ns3/
├── docs/
└── external/ns-3.47/     # ns-3.47 sources
```

## Commands (WSL)

```bash
cd ~/projects/uav-logistics-comms
source .venv/bin/activate
bash environment/bootstrap_wsl.sh   # idempotent

# ns-3
cd external/ns-3.47
./ns3 configure --enable-examples --enable-tests
./ns3 build
./test.py
./ns3 run first
```

## Stage gates

- `E0_ENVIRONMENT_READY` is required before `E1_DATA_INGESTION`
- Q1–Q4 must not start during E0
- The reference communication model is authoritative for optimization; ns-3 is a validation layer only

See `environment/ENVIRONMENT.md`, `environment/E0_REPORT.md`, `environment/VERSIONS.txt`.
