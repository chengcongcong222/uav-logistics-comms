# 华为杯 D 题：山区洪涝灾害下无人机运输与通信协同优化

本仓库为比赛工程环境与后续模型实现工作区。当前阶段仅完成 **E0 环境构建**，不实现 Q1–Q4 数学模型。

## 技术路线（冻结）

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

## 目录结构

```text
huawei-cup-d/
├── AGENTS.md
├── README.md
├── environment/          # 环境文档、版本、bootstrap 脚本
├── data/
│   ├── raw/              # 赛题原始数据（只读，禁止修改）
│   ├── processed/        # 解析后的派生数据
│   └── cache/            # 计算缓存
├── src/                  # 后续 Q1–Q4 实现（E0 不写算法）
├── validation/
│   ├── mathematical/     # Python smoke
│   ├── ns3/              # ns-3 smoke
│   └── robustness/
├── export/               # Python → ns-3 标准 CSV 接口
├── experiments/
├── results/
│   ├── e0/               # E0 smoke 输出
│   ├── q1/ … q4/
│   └── ns3/
├── docs/
└── external/ns-3.47/     # ns-3.47 源码
```

## 常用命令（WSL）

```bash
cd ~/projects/huawei-cup-d
source .venv/bin/activate
bash environment/bootstrap_wsl.sh   # 可重复执行

# ns-3
cd external/ns-3.47
./ns3 configure --enable-examples --enable-tests
./ns3 build
./test.py
./ns3 run first
```

## 阶段门禁

- `E0_ENVIRONMENT_READY` 后才可进入 `E1_DATA_INGESTION`
- E0 禁止实现 Q1–Q4
- 赛题通信模型是优化权威模型；ns-3 仅作验证层

详见 `environment/ENVIRONMENT.md`、`environment/E0_REPORT.md`、`environment/VERSIONS.txt`。
