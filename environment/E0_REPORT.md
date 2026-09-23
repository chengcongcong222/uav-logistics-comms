# E0 Environment Report

## 1. Decision

**E0_ENVIRONMENT_READY**

## 2. Host

Windows: Windows 10 Pro (build 26200 / NT 10.0.26200)  
WSL: 2  
Ubuntu: Ubuntu 24.04.4 LTS (noble)  
Kernel: 6.18.33.2-microsoft-standard-WSL2  

## 3. Toolchain

GCC: 13.3.0  
G++: 13.3.0  
Python: 3.12.3  
CMake: 3.28.3  
Ninja: 1.11.1  
Git: 2.43.0  

## 4. ns-3

Version: 3.47  
Tag: ns-3.47  
Commit: not-a-git-checkout (official tag archive)  
Tarball SHA256: 70ee07a934c2e0d2ae33820e6397ab106e9ae5a5a2c55216756f1922887dde3c  
Configure: SUCCESS (core/network/internet/mobility/wifi/applications/flow-monitor available)  
Build: SUCCESS  
Tests: **800 of 800 passed** (0 failed, 0 skipped, 0 crashed)  

## 5. Python

Venv: `/home/ccc/projects/uav-logistics-comms/.venv`  
Requirements: `environment/requirements.txt`  
Smoke test: SUCCESS  

- numpy=2.5.3
- scipy=1.18.1
- pandas=3.0.6
- openpyxl=3.1.5
- matplotlib=3.11.2
- rasterio=1.5.1
- pyproj=3.8.0

Outputs:

- `results/e0/python_smoke.csv`
- `results/e0/python_smoke.png`
- `results/e0/python_smoke_tmp.xlsx`

## 6. Integration smoke test

| Item | Result |
| --- | --- |
| WaypointMobility | OK (U01 3-waypoint path, end 200,0,50) |
| Wi-Fi | OK (802.11b / 2.4 GHz) |
| UDP | OK (U01 → G01) |
| FlowMonitor | OK |
| Python CSV import | OK (`export/e0_test_trace.csv` → WaypointMobilityModel) |

Smoke summary (`results/ns3/e0_smoke_summary.csv`):

```text
tx_packets=23
rx_packets=1
lost_packets=14
pdr=0.0434783
mean_delay_ms=9
u01_end_position=200,0,50
```

Acceptance:

- program builds and runs
- Waypoint trajectory updates correctly
- Wi-Fi link carries UDP
- FlowMonitor produces statistics
- tx_packets > 0
- rx_packets > 0
- PDR > 0

(E0 does not require PDR=100% and does not interpret wireless performance scientifically.)

## 7. Raw input data

Files found: **19** under `data/raw/`  
Modified: **NO**

Categories (names of local raw files intentionally omitted from this report):

- problem statement document (docx)
- submission template (xlsx)
- UAV fleet parameter workbooks (xlsx)
- demand / time-window workbook (xlsx)
- dispatch center / service area workbook (xlsx)
- communication link parameter workbook (xlsx)
- DEM (mat + tif)
- village points (csv + mat)
- water polygons (csv + mat)
- water lines (csv + mat)
- roads (csv + mat)
- geospatial notes (pdf) and map export (html)

Raw files remain read-only and are not tracked in git.

## 8. Generated artifacts

```text
AGENTS.md
README.md
.gitignore
environment/ENVIRONMENT.md
environment/VERSIONS.txt
environment/E0_REPORT.md
environment/requirements.txt
environment/bootstrap_wsl.sh
environment/fetch_ns3.sh
environment/build_ns3.sh
environment/run_ns3_tests.sh
environment/run_e0_smoke.sh
environment/setup_venv.sh
environment/collect_versions.sh
environment/probe_ns3_urls.sh
environment/ns3_configure.log
environment/ns3_build.log
environment/ns3_test.log
environment/ns3_first.log
environment/e0_smoke_build.log
environment/e0_smoke_run.log
environment/python_smoke.log
environment/trace_gen.log
validation/ns3/e0-smoke.cc
validation/mathematical/e0_python_smoke.py
validation/mathematical/e0_generate_trace.py
export/e0_test_trace.csv
results/e0/python_smoke.csv
results/e0/python_smoke.png
results/e0/python_smoke_tmp.xlsx
results/ns3/e0_smoke_summary.csv
external/ns-3.47/          # ns-3.47 sources (not in git)
external/download/ns-3.47.tar.bz2.sha256
```

## 9. Known limitations / remote status

1. ns-3 sources come from the official tag archive tarball (no `.git`); version is pinned by `NS3_TARBALL_SHA256` rather than a git commit hash.
2. Optional dependencies (Boost, GSL, LibXml2, SQLite, doxygen, Python bindings, etc.) are not installed; E0 required modules and tests are unaffected.
3. E0 smoke PDR is low (0.043) under simple propagation + mobility; **no** scientific wireless interpretation is claimed.
4. `data/raw` is inventoried only; full ingestion is deferred to E1.
5. GitHub remote is established at `chengcongcong222/uav-logistics-comms` (private). E0 has been pushed. `data/raw`, `.venv`, and `external/ns-3.47` are excluded from version control.

## 10. Next gate

**E1_DATA_INGESTION**

- Excel parsing
- DEM MAT/TIF parsing
- coordinate unification
- data integrity audit
- parameter cross-check
- standard dataset objects

E1 still does not implement Q2/Q3 optimization.
