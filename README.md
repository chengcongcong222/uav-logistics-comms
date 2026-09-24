# UAV Logistics & Relay Communication Lab

Current stage: **E8-A DONE; final optional Gamma 6 rescue closed; Q4 READY**.
The main remaining work is whole-contest submission-table integration and paper
assembly. Formal ns-3 is optional/late, not a gate for Q4.

- [Project status](results/project_status.json)
- [Q4 report and exact resource tradeoffs](results/q4/Q4_REPORT.md)
- [Q4 GPT handoff](results/q4/Q4_GPT_SYNC.md)
- [Q4 independent validation](results/q4/validation.json)
- [E8-A certified robustness costs](results/q3/E8_ROBUSTNESS_REPORT.md)
- [E8.1 final Gamma 6 rescue and diagnostic limits](results/q3/E81_CRITICAL_WINDOW_REPORT.md)
- [Paper main-result freeze and claim boundaries](docs/paper/MAIN_RESULTS_FREEZE_20260925.md)

## Current result authority

Q1 and Q2 retain their frozen results. E52/E6/E7 remain unchanged. E7 provides
eight formal Gamma-zero Q3 executions. Q4 fixes the time-priority Q3E7_001 source
and its whole-task communication dependencies; it enumerates all 15 two-group
and 25 three-group partitions of five unsplittable blocks.

Q4_READY means that partitions, exact minimum independent resource requirements
and inventory gaps are validated. It does **not** mean current inventory is
sufficient. Under this fixed source, even minimum-gap partitions require extra
resources: K2 needs one B UAV and one B battery; K3 needs two B UAVs, one C UAV,
two B batteries and one C battery. Balanced alternatives and the full Pareto
sets are supplied. No Q3 task times, routes or communication relations change.

E8-A has 23 validated points at Gamma 0/2/4 dB. The certified tested robustness
level is 4 dB; the true physical upper boundary is unknown. E8-B ended as
GAMMA6_NO_WITNESS_FOUND after one final bounded rescue, not as INFEASIBLE.
The full-interval reference-window site-cover count of three is not a lower
bound for free L1 timing: its midpoint instantaneous physical cover needs two.

## Review commands

```bash
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
.venv/bin/python validation/mathematical/e81_validate.py
.venv/bin/python validation/mathematical/q4_validate.py
.venv/bin/python validation/mathematical/test_q4_regressions.py
.venv/bin/python validation/mathematical/e8_gate.py
```

Model scopes: [E8](docs/model/Q3_ROBUSTNESS_E8_SEMANTICS.md),
[Q4](docs/model/Q4_PARTITION_SEMANTICS.md). The two Q4 xlsx files are verified
draft Q4 pages, not the final combined contest workbook. Raw data are immutable.
Legacy modified top-level Q2 CSVs are not authoritative synchronized packages.

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
