# P1.3-A 复现

环境：WSL Ubuntu-24.04，仓库 `/home/ccc/projects/uav-logistics-comms`，Python 虚拟环境 `.venv`。版本、时限、线程数、CPU 记录见 `environment.json`。原始数据与既有 P1/P1.2 验证包须可读；不从外部解导入路线。

本轮基于 `dc49b4267c5860d8a6e10728cd629be1009cacc3`，分支 `p1-3a-finite-domain-audit`。不要覆盖已提交运行目录。各轮执行代码分别保存在 `source_snapshot`、`source_snapshot_v2`、`source_snapshot_v3`。最终权威运行为 A11/A03 v2、AN01 v3；AN01 v3 关闭 MILP 预处理，其他数学约束不变。

## 轻量检查

在仓库根目录执行：

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 .venv/bin/python -m unittest src.bench_p1_3a.test_model -v
.venv/bin/python -m src.bench_p1_3a.verify
.venv/bin/python -m src.bench_p1_3a.transport_bounds
.venv/bin/python -m src.bench_p1_3a.report
```

`verify` 从现有 NPZ 矩阵重算有理数证书，不运行优化。后三个命令会重写对应派生汇总；如需保持提交文件逐字不变，请在隔离副本中运行。时间和版本字段可能因环境变化而改变。

## 重新运行有限域求解

使用不存在的新 revision 名，三个结构可顺序执行。固定开发种子 26092511，每个单目标 MIP 限时 90 s，LP 限时 60 s；每个求解器 1 线程。这不是严格等 CPU 方法比较。计费同时保留过程 CPU 和求解器各阶段 CPU；候选独立物理验证另在包内记录。

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 .venv/bin/python -m src.bench_p1_3a.run A11 --revision replay_01 --limit 90
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 .venv/bin/python -m src.bench_p1_3a.run AN01 --revision replay_01 --no-presolve --limit 90
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 .venv/bin/python -m src.bench_p1_3a.run A03 --revision replay_01 --limit 90
```

运行器拒绝覆盖已有 revision/结构目录，重新建立私有通信需求与站点关系。`inputs.json` 对每个内部源执行包绑定 witness 和验证 SHA-256；`admit.py` 还检查它们与基准提交的 P1.2 全文件清单一致。6 个代表包的新核验输出在 admission 目录。

如需重做准入，应在隔离工作副本中将既有新阶段目录整体保留到另一名称，再运行 `.venv/bin/python -m src.bench_p1_3a.admit`；不要删除或覆盖旧 Q3、Q4、提交表。`--resume` 只为已完成、哈希未变的中断核验恢复设计。首轮报告序列化异常记录保留在 diagnostics。

汇总脚本以 `runs/v2/A11`、`runs/v2/A03`、`runs/v3/AN01` 为本轮权威运行；新的 replay 目录不会自动替换正式汇总。需要人工检查新运行和作用域后再另建汇总，不能因运行时间不同就覆盖既有结论。v2 AN01 的能耗求解因对偶界超过已验证可行上界而触发断言，其未落盘节点/CPU 不可恢复；不要当作完整正式记录，完整重跑见 v3。

## 原始证据位置

- `inputs.json`、`warm_readmission.json`：准入来源、输入/验证哈希、6 个代表包完整重核验。
- `runs/<权威版本>/<结构>/group_mode_catalogue.json`：完整中继分组和端点次序目录及站点集合（A11/A03 为 v2，AN01 为 v3）。
- `runs/<权威版本>/<结构>/warm_embedding.json`：所有合格暖启动嵌入完整 MILP 的残差。
- `runs/<权威版本>/<结构>/anchors/<目标>/model.npz`：目标、约束矩阵、行界、变量界、整数标记。
- 同目录 `lp_lower_bound_certificate.json`：分子/分母、对偶乘子、矩阵哈希。
- 同目录 `solver_incumbent.npy`、可选 `polished_incumbent.npy`：原求解器候选和仅用于原始可行解修复的结果。
- 结构目录的 `extreme_results.json`：原始 solver bound、gap、状态、节点、CPU；不以终止标签替代独立核验。
- 根目录 `solver_bounds.json`：保守接受的证书下界，与原始分支定界结果分列。
- `protection_check.json`：12680 个既有文件、main 和执行代码快照核对。
- `artifact_manifest.json`：本阶段最终文件哈希清单（排除清单本身及 Python 缓存）。

本轮到 P1.3-A 停止；复现命令不启动 P1.3-B、列生成、正式多种子比较或替换主例。
