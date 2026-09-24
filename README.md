# UAV Logistics & Relay Communication Lab

UAV logistics trajectory planning and relay-communication validation workspace.
Python models produce standardized trajectories/schedules; ns-3.47 validates mobility + Wi-Fi + UDP + FlowMonitor.

Current stage: **E6 relay resource scheduling READY**. P01, P02 and P03 have
independently validated execution schedules using two relay UAVs and six energy
components. E7 has not started. See the [E6 report](results/q3/E6_RESOURCE_REPORT.md)
and [Chinese GPT handoff](results/q3/E6_GPT_SYNC.md).

## Current result authority

- Transport baseline: `results/q2/pareto_schedules/P01..P03/`. Legacy top-level
  Q2 files are not a synchronized package.
- E52 inputs remain unchanged; their gate is `results/q3/e52_rescue/validation.json`.
- Executable E6 schedules, guarded communication assignments, independent
  audits and metrics: `results/q3/e6/`.
- Current gate: [results/q3/e6/validation.json](results/q3/e6/validation.json),
  bound to input, output and source hashes.
- Representative P01: 28 transport sorties, 12 relay sorties, 42,380.952171 s
  total transport delay, 13,895.966266 s joint makespan. All three plans satisfy
  hard deadlines and the numerical full-flight communication audit.
- Candidate pools remain incomplete. These are feasible execution witnesses,
  not globally minimum-delay schedules. Small communication margins and
  substantial soft-deadline costs remain explicit limitations.
- [E6 model semantics](docs/model/Q3_RELAY_E6_SEMANTICS.md).

```bash
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
.venv/bin/python -m src.q3.e6_replay
.venv/bin/python validation/mathematical/e6_test_regressions.py
for p in P01 P02 P03; do
  .venv/bin/python validation/mathematical/e6_validate_pool.py --plan "$p"
  .venv/bin/python validation/mathematical/e6_validate.py --plan "$p"
done
.venv/bin/python validation/mathematical/e6_validate.py --plan P01 --step .25
.venv/bin/python validation/mathematical/e6_gate.py
```

Replay reconstructs the committed witness without depending on time-limited
MILP search. Re-exporting requires rerunning independent validation before
issuing the gate. Earlier E52 reproduction instructions remain in
[the E52 report](results/q3/E52_REPORT.md). The E0 environment notes below
remain historical setup instructions.

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
