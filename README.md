# UAV Logistics & Relay Communication Lab

Current stage: **Final Q2 equal-CPU five-seed comparison complete; G2 main preserved; paper drafting**.

- [Final 180 CPU-second, five-seed Q2 experiment](results/ablation180_v2/ABLATION_REPORT.md)
- [Current combined evidence gate](results/ablation180_v2/gate.json)
- [Latest GPT handoff](results/ablation180_v2/GPT_SYNC.md)
- [Paper main-text draft](docs/paper/G2_PAPER_MAIN_DRAFT.md)
- [Paper claims and evidence](docs/paper/G2_EVIDENCE_MAP.md)
- [G2 complete report: geometry, own/control results, limits](results/reset/RESET_REPORT.md)
- [G2 GPT handoff](results/reset/RESET_GPT_SYNC.md)
- [G2 gate and artifact hashes](results/reset/gate.json)
- [Combined submission workbook](results/reset/submission/结果提交表_G2_自主主方案.xlsx)
- [New Q4 based on the autonomous main](results/reset/q4/Q4_REPORT.md)
- [Reproduction and independent review](results/reset/REPRODUCE.md)
- [Project status](results/project_status.json)
- [Historical XB1 external-structure audit](results/xb1/XB1_REPORT.md)

## Current result authority

Flight geometry is G2_UTM49N_STRAIGHT_NATIVE_SUPERCOVER_V1: UTM49N straight
segments traversed against the native DEM, with touched-edge/corner supercover
and fail-closed invalid cells. Transport and relay outbound/return use the same
definition. All 240 transport legs have a second numerical geometry check.

The autonomous generator reads local box and resource data, without importing
XB or supplied R box groups/routes/types. Its bounded 2903-pattern pool and
joint integer scheduling produce zero-lateness Q2 witnesses A03/A11/A12 and
a low-energy soft-lateness comparison AS01. External controls B01/B02 keep
their XB provenance and the same G2 physical model.

The formal autonomous Q3 example is A11_Q3_001: J_late=0, J_norm=0.467343499,
7191.582229 s, 70.464235420 kWh, 25 transport sorties and 5 relay sorties,
within the original two relay UAVs and six-component pool. It is faster than
the external time representative but consumes more energy. All 21 G2 Q3
packages pass independent 0.5 s full-flight checks; main/control representatives
also pass 0.25 s. Seven active dominance counterexamples were found and audited.

These are finite-archive nondominated witnesses, not a global Pareto proof.
One dependency-driven structure reconstruction was executed and audited; it
does not prove that synchronized reconstruction outperforms strong methods.
The final Q2 comparison now uses 180 process CPU seconds, one core and five seeds
for three implementations. All 141 in-budget checkpoints pass independent audits.
Both pool methods achieve zero lateness in 5/5 seeds; uniform LNS achieves 0/5.
Active challenges add 13 verified Q2 dominance witnesses and improve auxiliary
delivery timing. Q3 multi-seed method performance remains untested. This is an
equal enforced CPU-cap comparison, not a global method ranking.

New Q4 freezes A11_Q3_001 and has six dependency blocks: 31/90 partitions for
K=2/3, minimum typed inventory gaps 2/4 units. The workbook includes the official
six sheets plus explicit Q3 transport/delivery supplements: Q2 transport clocks
must not be paired with the Q3 relay schedule.

Historical XB1/E6/E7/E8/Q4 outputs stay versioned and unchanged. Old E8 Gamma_cert=4
applies only to the old P01 structure; the G2 main is certified here only at
Gamma=0. Gamma6 and new ns-3 experiments are stopped. Algorithm expansion is stopped. Paper main text is drafted; references,
final formatting and submission review remain. The old G2 gate is historical
evidence pinned to 4ae3d2d; its mathematical artifacts and workbook are unchanged.
The new gate records the completed Q2 comparison with its explicit scope.

Legacy modified top-level Q2 CSVs are not authoritative synchronized packages.
Use the G2 gate/reproduction entry points above. Raw data are immutable.

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
