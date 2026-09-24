# UAV Logistics & Relay Communication Lab

Current stage: **XB1 closed: external Q2 structures verified and new Q3 executions validated**.

- [XB1 report: results, attribution, DEM findings and limits](results/xb1/XB1_REPORT.md)
- [XB1 GPT handoff](results/xb1/XB1_GPT_SYNC.md)
- [XB1 gate and artifact hashes](results/xb1/gate.json)
- [Project status](results/project_status.json)
- [Q4 historical baseline report](results/q4/Q4_REPORT.md)
- [E8 robustness on the old P01 structure](results/q3/E8_ROBUSTNESS_REPORT.md)

## Current result authority

Q2 XB01/XB02 import only attributed box groups, visit order and aircraft types
from a pinned public external result. Local physics, schedules and independent
validation replace all external clocks, metrics and feasibility claims. Both
have zero weighted lateness and dominate old P01-P03 under the frozen ordering.

Nine new Gamma-zero Q3 executions passed independent 0.5 s full-flight audits;
one representative per structure also passed 0.25 s. Recommended main example
XB01_Q3_001 has J_late=0, 8214.302952 s, 69.731633 kWh, 24 transport sorties and
six relay sorties, using the original two relay UAVs and six energy components.
It dominates all eight old E7 executions. External structure attribution is
mandatory; these are not claimed as independently discovered box groups.

Old E6/E7/E8 and Q4 packages remain immutable historical evidence. Q4 resource
requirements apply only to Q3E7_001 and must be recomputed for the new main
example. E8 Gamma_cert=4 and robustness costs apply only to the old P01
structure, not to XB01/XB02. Gamma6 rescue remains closed; ns-3 remains optional.

XB1 also found that frozen transport geometry used roughly 30 m DEM sampling,
not exact cell traversal. Exact-cell sensitivity for all five Q2 structures
preserves the improvement conclusion, but exact-cell Q3 has not been rebuilt.
Final DEM scope and new Q4/submission integration are the next tasks; previous
paper-result freezing is reopened. See the report for explicit numerical limits.

## Review commands

Use OMP_NUM_THREADS=1, MKL_NUM_THREADS=1, OPENBLAS_NUM_THREADS=1.

- .venv/bin/python validation/mathematical/xb1_validate.py
- .venv/bin/python -m unittest discover -s validation/mathematical -p test_xb1_regressions.py -v
- .venv/bin/python validation/mathematical/xb1_gate.py

Full solve/replay/audit commands are in the XB1 report. Raw data are immutable.
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
