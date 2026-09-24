# UAV Logistics & Relay Communication Lab

UAV logistics trajectory planning and relay-communication validation workspace.
Python models produce standardized trajectories/schedules; ns-3.47 validates mobility + Wi-Fi + UDP + FlowMonitor.

Current stage: **E7 Q3 joint Pareto optimization READY**. Eight independently
validated nondominated execution packages improve on E6 P01. Transport box
assignment, routes and types remain fixed: L1 resource/timing and relay changes
were sufficient for substantial gains, so L2/L3 were not activated.
E8 robustness, formal ns-3 experiments and Q4 have not started.

- [E7 complete report and ablation](results/q3/E7_JOINT_PARETO_REPORT.md)
- [E7 GPT audit handoff](results/q3/E7_GPT_SYNC.md)
- [Validated Pareto table](results/q3/e7/pareto_solutions.csv)
- [Artifact-bound E7 gate](results/q3/e7/validation.json)
- [E7 model and optimization semantics](docs/model/Q3_JOINT_E7_SEMANTICS.md)

Best known TimelinessKey: `(87005.086170, 0.558470231)`, versus E6 P01
`(648615.604679, 0.746568947)`. Under a 2% lateness budget, a validated
execution finishes at 11,304.755580 s using 78.319613 kWh and nine relay
sorties. There are tradeoffs between timeliness, makespan and energy; this is
a bounded known frontier, not a complete global Pareto frontier.

## Current result authority

- Frozen transport baseline: `results/q2/pareto_schedules/P01..P03/`.
  Legacy top-level Q2 CSVs are not a synchronized package.
- E52 and E6 remain unchanged and retain their own validated gates.
- Current Q3 executions: `results/q3/e7/solutions/Q3E7_001..008/`.
- Formal objectives exclude transport shift. `TimelinessKey` is lexicographic;
  final selection uses epsilon budgets and exact official-metric nondominance.
- Gamma_C remains 0 dB. Full-flight numerical validation is authoritative;
  construction guards are not an analytical continuity or robustness proof.

```bash
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
# Select by epsilon budget, reconstruct the package and independently validate.
.venv/bin/python -m src.q3.e7_replay --epsilon .02 --objective energy \
  --output results/q3/e7/generated/my_epsilon02_energy
.venv/bin/python -m src.q3.e7_replay --check-all
.venv/bin/python validation/mathematical/e7_gate.py
# Rebuild the bounded experiment, controls, audits and gate from frozen E6 input.
.venv/bin/python -m src.q3.e7_run
```

The E6 [report](results/q3/E6_RESOURCE_REPORT.md) and its replay instructions
remain available. The E0 setup notes below describe the frozen environment.

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
