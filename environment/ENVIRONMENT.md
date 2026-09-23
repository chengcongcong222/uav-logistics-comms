# ENVIRONMENT — 华为杯 D 题 E0 可复现开发环境

本文档描述本机已验证的开发环境，供另一台机器基本复现。

## 1. Host / OS

| 项目 | 值 |
| --- | --- |
| Windows版本 | Windows 10 Pro (build 26200 / NT 10.0.26200) |
| WSL版本 | 2 |
| Ubuntu版本 | Ubuntu 24.04.4 LTS (noble) |
| Kernel版本 | 6.18.33.2-microsoft-standard-WSL2 |
| 项目根目录 | `/home/ccc/projects/huawei-cup-d` |
| ns-3根目录 | `/home/ccc/projects/huawei-cup-d/external/ns-3.47` |
| 数据目录 | `data/raw`（只读）、`data/processed`、`data/cache` |

> 主工程位于 WSL Linux 文件系统（`/home/ccc/...`），不在 `/mnt/c/...`。

## 2. Toolchain

| 工具 | 版本 |
| --- | --- |
| GCC | 13.3.0 |
| G++ | 13.3.0 |
| Python | 3.12.3 |
| CMake | 3.28.3 |
| Ninja | 1.11.1 |
| Git | 2.43.0 |
| ccache | 4.9.1 |

## 3. ns-3

| 项目 | 值 |
| --- | --- |
| 版本 | **3.47**（`VERSION` 文件） |
| Tag | `ns-3.47` |
| Commit | 源码来自官方 tag 归档，无 `.git`；以 tarball SHA256 固定 |
| Tarball SHA256 | `70ee07a934c2e0d2ae33820e6397ab106e9ae5a5a2c55216756f1922887dde3c` |
| 下载 URL | `https://gitlab.com/nsnam/ns-3-dev/-/archive/ns-3.47/ns-3-dev-ns-3.47.tar.bz2` |
| 说明 | 采用纯 ns-3.47 源码树；未使用 ns-allinone 构建体系；未使用 ns-3-dev HEAD |

### 3.1 必需模块（configure 确认）

`core`, `network`, `internet`, `mobility`, `wifi`, `applications`, `flow-monitor` — 全部可构建。

### 3.2 构建命令

```bash
cd /home/ccc/projects/huawei-cup-d/external/ns-3.47
./ns3 configure --enable-examples --enable-tests
./ns3 build
```

日志：

- `environment/ns3_configure.log`
- `environment/ns3_build.log`

### 3.3 测试命令

```bash
cd /home/ccc/projects/huawei-cup-d/external/ns-3.47
./test.py
./ns3 run first
```

日志：

- `environment/ns3_test.log` — **800/800 PASS，0 FAIL**
- `environment/ns3_first.log` — 官方 tutorial `first` 正常结束

## 4. Python 环境

| 项目 | 值 |
| --- | --- |
| Venv | `/home/ccc/projects/huawei-cup-d/.venv` |
| Requirements | `environment/requirements.txt` |

核心包：

```
numpy==2.5.3
scipy==1.18.1
pandas==3.0.6
openpyxl==3.1.5
matplotlib==3.11.2
rasterio==1.5.1
pyproj==3.8.0
```

E0 **未**安装 PyTorch / TensorFlow / Ray / Stable-Baselines。

### 4.1 创建 / 激活

```bash
cd /home/ccc/projects/huawei-cup-d
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r environment/requirements.txt
```

或重复执行：

```bash
bash environment/bootstrap_wsl.sh   # idempotent
```

## 5. Smoke Test 命令

### 5.1 Python smoke

```bash
source .venv/bin/activate
python validation/mathematical/e0_python_smoke.py
```

输出：`results/e0/python_smoke.csv`、`results/e0/python_smoke.png`

### 5.2 Python → CSV 轨迹

```bash
python validation/mathematical/e0_generate_trace.py
```

输出：`export/e0_test_trace.csv`

### 5.3 ns-3 smoke（含 CSV 轨迹回放）

```bash
bash environment/run_e0_smoke.sh
```

或手动：

```bash
cp validation/ns3/e0-smoke.cc external/ns-3.47/scratch/
cd external/ns-3.47
./ns3 build e0-smoke
./ns3 run "e0-smoke --trace=/home/ccc/projects/huawei-cup-d/export/e0_test_trace.csv --summary=/home/ccc/projects/huawei-cup-d/results/ns3/e0_smoke_summary.csv"
```

输出：`results/ns3/e0_smoke_summary.csv`

## 6. CSV 接口规范（E0 最简五列）

```text
node_id,time,x,y,z
```

后续 Q2/Q3 将扩展为：

```text
node_id,time,x,y,z,mode,task_id,relay_id
```

E0 仅验证最简五列版本。

## 7. 数据规则

- `data/raw` **只读**，禁止修改原 Excel / DEM / 原始文件。
- 派生结果写入 `data/processed`、`data/cache`、`export/`、`results/`。
- E0 只检查 raw 文件存在性，不做正式数据解析。

## 8. 复现步骤摘要

1. Windows 启用 WSL2，安装 Ubuntu 24.04。
2. 在 WSL 中执行 `bash environment/bootstrap_wsl.sh`。
3. 运行 `bash environment/fetch_ns3.sh` 获取 ns-3.47。
4. 运行 `bash environment/build_ns3.sh`。
5. 运行 `bash environment/run_ns3_tests.sh`。
6. 运行 `bash environment/run_e0_smoke.sh`。
7. 核对 `environment/VERSIONS.txt` 与本文件。

## 9. 维护者须知

- 禁止 `sudo ./ns3 ...`
- 禁止擅自更换 ns-3 版本
- 禁止在 E0–E9 中重新定义赛题通信模型（ns-3 仅为验证层）
- 禁止 AODV/OLSR 替代中继调度；禁止中继-中继多跳
