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
Commit: not-a-git-checkout（官方 tag 归档源码）  
Tarball SHA256: 70ee07a934c2e0d2ae33820e6397ab106e9ae5a5a2c55216756f1922887dde3c  
Configure: SUCCESS（core/network/internet/mobility/wifi/applications/flow-monitor 均可用）  
Build: SUCCESS  
Tests: **800 of 800 passed**（0 failed, 0 skipped, 0 crashed）  

## 5. Python

Venv: `/home/ccc/projects/huawei-cup-d/.venv`  
Requirements: `environment/requirements.txt`  
Smoke test: SUCCESS  

- numpy=2.5.3
- scipy=1.18.1
- pandas=3.0.6
- openpyxl=3.1.5
- matplotlib=3.11.2
- rasterio=1.5.1
- pyproj=3.8.0

输出：

- `results/e0/python_smoke.csv`
- `results/e0/python_smoke.png`
- `results/e0/python_smoke_tmp.xlsx`

## 6. Integration smoke test

| 项目 | 结果 |
| --- | --- |
| WaypointMobility | OK（U01 轨迹 3 个 waypoint，终点 200,0,50） |
| Wi-Fi | OK（802.11b / 2.4 GHz） |
| UDP | OK（U01 → G01） |
| FlowMonitor | OK |
| Python CSV import | OK（`export/e0_test_trace.csv` → WaypointMobilityModel） |

Smoke 统计（`results/ns3/e0_smoke_summary.csv`）：

```text
tx_packets=23
rx_packets=1
lost_packets=14
pdr=0.0434783
mean_delay_ms=9
u01_end_position=200,0,50
```

验收：

- 程序成功编译 / 成功运行
- Waypoint 轨迹正常更新
- Wi-Fi 链路可传输 UDP
- FlowMonitor 输出统计
- tx_packets > 0
- rx_packets > 0
- PDR > 0

（本阶段不要求 PDR=100%，不对无线性能做科学解释。）

## 7. Raw contest data

Files found: **19**（已复制到 `data/raw/`，清单见下）  
Modified: **NO**

```text
data/raw/山区洪涝灾害下无人机运输与通信协同优化.docx
data/raw/结果提交模板.xlsx
data/raw/数据/无人机应急物资运输基础数据/中继无人机数据.xlsx
data/raw/数据/无人机应急物资运输基础数据/物资需求与配送时限.xlsx
data/raw/数据/无人机应急物资运输基础数据/调度中心与服务区.xlsx
data/raw/数据/无人机应急物资运输基础数据/运输无人机数据.xlsx
data/raw/数据/无人机应急物资运输基础数据/通信链路参数.xlsx
data/raw/数据/镇龙乡地理空间数据/镇龙乡地理空间数据说明.pdf
data/raw/数据/镇龙乡地理空间数据/镇龙乡地理空间详情地图.html
data/raw/数据/镇龙乡地理空间数据/镇龙乡及周边地理数据/数字高程模型数据（DEM）/镇龙乡及周边30米DEM.mat
data/raw/数据/镇龙乡地理空间数据/镇龙乡及周边地理数据/数字高程模型数据（DEM）/镇龙乡及周边30米DEM.tif
data/raw/数据/镇龙乡地理空间数据/镇龙乡及周边地理数据/村镇点位/镇龙乡及周边村镇点位.csv
data/raw/数据/镇龙乡地理空间数据/镇龙乡及周边地理数据/村镇点位/镇龙乡及周边村镇点位.mat
data/raw/数据/镇龙乡地理空间数据/镇龙乡及周边地理数据/水体（面）/镇龙乡及周边水体.csv
data/raw/数据/镇龙乡地理空间数据/镇龙乡及周边地理数据/水体（面）/镇龙乡及周边水体.mat
data/raw/数据/镇龙乡地理空间数据/镇龙乡及周边地理数据/水系（线）/镇龙乡及周边水系.csv
data/raw/数据/镇龙乡地理空间数据/镇龙乡及周边地理数据/水系（线）/镇龙乡及周边水系.mat
data/raw/数据/镇龙乡地理空间数据/镇龙乡及周边地理数据/道路/镇龙乡及周边道路.csv
data/raw/数据/镇龙乡地理空间数据/镇龙乡及周边地理数据/道路/镇龙乡及周边道路.mat
```

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
external/ns-3.47/          # ns-3.47 官方源码（不进入 git）
external/download/ns-3.47.tar.bz2.sha256
```

## 9. Known limitations

1. ns-3 源码为 GitLab tag 归档 tarball，无 `.git` 目录；用 `NS3_TARBALL_SHA256` 固定版本，而非 git commit hash。
2. 可选依赖未安装（Boost、GSL、LibXml2、SQLite、doxygen、Python bindings 等），不影响 E0 必需模块与测试。
3. E0 smoke 的 PDR 较低（0.043），属简单传播 + 移动场景预期现象；**不做**无线性能科学解释。
4. `data/raw` 仅完成导入与清单记录，尚未做 E1 级解析。
5. 未创建远程 Git 仓库，未 push。

## 10. Next gate

**E1_DATA_INGESTION**

- Excel 解析
- DEM MAT/TIF 解析
- 坐标统一
- 数据完整性审计
- 题面参数核对
- 标准数据对象生成

E1 仍不进行 Q2/Q3 优化。
