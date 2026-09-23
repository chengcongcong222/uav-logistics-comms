# ENVIRONMENT — E0 reproducible lab (WSL2 + ns-3.47)

This document describes the verified local development environment for reproduction on another machine.

## 1. Host / OS

| Item | Value |
| --- | --- |
| Windows | Windows 10 Pro (build 26200 / NT 10.0.26200) |
| WSL | 2 |
| Ubuntu | Ubuntu 24.04.4 LTS (noble) |
| Kernel | 6.18.33.2-microsoft-standard-WSL2 |
| Project root | `/home/ccc/projects/uav-logistics-comms` |
| ns-3 root | `/home/ccc/projects/uav-logistics-comms/external/ns-3.47` |
| Data dirs | `data/raw` (immutable), `data/processed`, `data/cache` |

> The main tree lives on the WSL Linux filesystem (`/home/ccc/...`), not under `/mnt/c/...`.

## 2. Toolchain

| Tool | Version |
| --- | --- |
| GCC | 13.3.0 |
| G++ | 13.3.0 |
| Python | 3.12.3 |
| CMake | 3.28.3 |
| Ninja | 1.11.1 |
| Git | 2.43.0 |
| ccache | 4.9.1 |

## 3. ns-3

| Item | Value |
| --- | --- |
| Version | **3.47** (`VERSION` file) |
| Tag | `ns-3.47` |
| Commit | official tag archive (no `.git`); fixed by tarball SHA256 |
| Tarball SHA256 | `70ee07a934c2e0d2ae33820e6397ab106e9ae5a5a2c55216756f1922887dde3c` |
| Source URL | `https://gitlab.com/nsnam/ns-3-dev/-/archive/ns-3.47/ns-3-dev-ns-3.47.tar.bz2` |
| Notes | pure ns-3.47 tree; no ns-allinone build system; not ns-3-dev HEAD |

### 3.1 Required modules (configure confirmed)

`core`, `network`, `internet`, `mobility`, `wifi`, `applications`, `flow-monitor` — all buildable.

### 3.2 Build

```bash
cd /home/ccc/projects/uav-logistics-comms/external/ns-3.47
./ns3 configure --enable-examples --enable-tests
./ns3 build
```

Logs:

- `environment/ns3_configure.log`
- `environment/ns3_build.log`

### 3.3 Tests

```bash
cd /home/ccc/projects/uav-logistics-comms/external/ns-3.47
./test.py
./ns3 run first
```

Logs:

- `environment/ns3_test.log` — **800/800 PASS, 0 FAIL**
- `environment/ns3_first.log` — official tutorial `first` completed

## 4. Python environment

| Item | Value |
| --- | --- |
| Venv | `/home/ccc/projects/uav-logistics-comms/.venv` |
| Requirements | `environment/requirements.txt` |

Core packages:

```
numpy==2.5.3
scipy==1.18.1
pandas==3.0.6
openpyxl==3.1.5
matplotlib==3.11.2
rasterio==1.5.1
pyproj==3.8.0
```

E0 does **not** install PyTorch / TensorFlow / Ray / Stable-Baselines.

### 4.1 Create / activate

```bash
cd /home/ccc/projects/uav-logistics-comms
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r environment/requirements.txt
```

Or re-run:

```bash
bash environment/bootstrap_wsl.sh   # idempotent
```

## 5. Smoke test commands

### 5.1 Python smoke

```bash
source .venv/bin/activate
python validation/mathematical/e0_python_smoke.py
```

Outputs: `results/e0/python_smoke.csv`, `results/e0/python_smoke.png`

### 5.2 Python → CSV trajectory

```bash
python validation/mathematical/e0_generate_trace.py
```

Output: `export/e0_test_trace.csv`

### 5.3 ns-3 smoke (CSV trajectory replay)

```bash
bash environment/run_e0_smoke.sh
```

Or manually:

```bash
cp validation/ns3/e0-smoke.cc external/ns-3.47/scratch/
cd external/ns-3.47
./ns3 build e0-smoke
./ns3 run "e0-smoke --trace=/home/ccc/projects/uav-logistics-comms/export/e0_test_trace.csv --summary=/home/ccc/projects/uav-logistics-comms/results/ns3/e0_smoke_summary.csv"
```

Output: `results/ns3/e0_smoke_summary.csv`

## 6. CSV interface (E0 minimal five columns)

```text
node_id,time,x,y,z
```

Later stages extend to:

```text
node_id,time,x,y,z,mode,task_id,relay_id
```

E0 validates only the minimal five-column form.

## 7. Data rules

- `data/raw` is **read-only**; never rewrite original Excel / DEM / source files.
- Derived outputs go to `data/processed`, `data/cache`, `export/`, `results/`.
- E0 only checks raw file presence; full ingestion is deferred to E1.

## 8. Reproduction summary

1. Enable WSL2 on Windows and install Ubuntu 24.04.
2. In WSL run `bash environment/bootstrap_wsl.sh`.
3. Run `bash environment/fetch_ns3.sh` to fetch ns-3.47.
4. Run `bash environment/build_ns3.sh`.
5. Run `bash environment/run_ns3_tests.sh`.
6. Run `bash environment/run_e0_smoke.sh`.
7. Cross-check `environment/VERSIONS.txt` and this file.

## 9. Maintainer notes

- Do not run `sudo ./ns3 ...`
- Do not silently change the ns-3 version
- Do not redefine the reference communication model (ns-3 is validation only)
- Do not replace the relay schedule with AODV/OLSR; no relay-to-relay multihop
