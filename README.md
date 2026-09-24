# UAV Logistics & Relay Communication Lab

Current stage: **E8 robustness study PARTIAL — Gamma 6 dB unresolved**.
Gamma 0/2/4 dB have 8/5/10 independently validated Pareto execution points.
Gamma 6 has communication candidates for every demand but no executable joint
resource witness within this bounded search. Physical infeasibility is not
proven. Formal ns-3 and Q4 remain WAIT.

- [E8 full report and robustness costs](results/q3/E8_ROBUSTNESS_REPORT.md)
- [E8 GPT review handoff](results/q3/E8_GPT_SYNC.md)
- [Validated Pareto family](results/q3/e8/pareto_family.csv)
- [Artifact-bound E8 review](results/q3/e8/validation.json)
- [E8 semantics and reproduction](docs/model/Q3_ROBUSTNESS_E8_SEMANTICS.md)
- [Preserved E7 report](results/q3/E7_JOINT_PARETO_REPORT.md)

## Current result authority

Frozen transport baselines are under `results/q2/pareto_schedules/P01..P03/`;
legacy top-level Q2 CSVs are not synchronized packages. E52/E6/E7 are unchanged.
E8 fixes the P01 transport structure, allows L1 timing/resource changes and
requires Gamma on the direct link and both relay hops. Gamma 0 exactly preserves
the eight final E7 executions.

Validated E8 packages are in `results/q3/e8/gamma_00/solutions/`,
`gamma_02/solutions/`, and `gamma_04/solutions/`. There is no validated Gamma 6
package. Numerical full-flight validation does not constitute an analytic
continuous-time guarantee.

```bash
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
.venv/bin/python -m src.q3.e8_replay --check-all
.venv/bin/python validation/mathematical/e8_gate.py
.venv/bin/python -m src.q3.e8_replay --gamma 4 --epsilon .02 --objective energy --output results/q3/e8/generated/g4_e02_energy
.venv/bin/python validation/mathematical/e8_validate.py --directory results/q3/e8/generated/g4_e02_energy --step .5
```

The E8 gate remains partial while Gamma 6 is unresolved. An empty known frontier
or a restricted MILP infeasibility result does not prove the original scenario
impossible.

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
