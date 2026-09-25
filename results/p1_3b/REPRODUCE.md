# P1.3-B 复现

WSL Ubuntu-24.04，仓库 `/home/ccc/projects/uav-logistics-comms`。基准提交 `62e8d6b72fe9305c00d228d820a065ddefb22524`，开发分支 `p1-3b-full-pool-audit`。原数据、G2 几何、P1 的 118 冻结站点输入以及历史自主 Q2 包须可读。

## 隔离依赖

原 `.venv` 不安装或升级依赖。新增 CP-SAT 及必要依赖单独放在 `.deps_p13b`，该目录不入提交。

```bash
.venv/bin/python -m pip install --target .deps_p13b --no-deps \
  'ortools==9.14.6206' 'protobuf==6.31.1' 'absl-py==2.5.0' 'immutabledict==4.3.1'
export PYTHONPATH="$PWD/.deps_p13b:$PWD"
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
```

`environment.json` 记录实际 Python、SciPy、NumPy、Pandas 版本。最初临时环境/失效 pip 启动脚本的安装诊断保留在日志中；最终命令使用原 Python 的 `-m pip --target`，不是改变原环境。

## 已提交证据的检查

以下命令在仓库根执行。复算会重写对应派生验证汇总；希望保持整个工作树字节不变时，请先使用隔离工作副本。

```bash
.venv/bin/python -m unittest src.bench_p1_3b.test_models -v
.venv/bin/python -m src.bench_p1_3b.verify
.venv/bin/python -m src.bench_p1_3b.report
.venv/bin/python -m src.bench_p1_3b.seal
```

测试覆盖保守区间、重复模式、充电资源瓶颈、完整提示可行性、外松弛包含已验证 A11 排程，以及并行机工作量条件。`verify` 不重新优化，独立重算全部有理数证书并检查所有 Q2/Q3 验证文件的产物哈希。

## 重新求解运输层

使用全新 run 名，运行器拒绝覆盖既有名称。实际主运行是 `makespan_v3`、`sorties_v3`、`J_norm_v3`、`energy_v3`，四个独立单目标，不是某个任意权重组合。

```bash
.venv/bin/python -m src.bench_p1_3b.transport makespan --name replay_time --limit 180 --workers 4
.venv/bin/python -m src.bench_p1_3b.transport sorties --name replay_count --limit 90 --workers 4
.venv/bin/python -m src.bench_p1_3b.transport J_norm --name replay_norm --limit 90 --workers 4
.venv/bin/python -m src.bench_p1_3b.transport energy --name replay_energy --limit 90 --workers 4
```

开发种子为 26092511。四工作线程的搜索不承诺同一 seed 逐比特相同；配置、原始模型、原始日志、所有不同结构的改进候选、CPU/wall time、分支和冲突均保存。这不是严格等 CPU 多种子实验。

模式池准入及连续外松弛重建分别为：

```bash
.venv/bin/python -m src.bench_p1_3b.common
.venv/bin/python -m src.bench_p1_3b.bounds
```

这两个命令使用固定阶段路径，会重写阶段派生文件，因此只在隔离复现副本执行。原模式池必须逐字匹配基准提交，严禁重跑生成器替换池。完整旧版/中间舍入版本矩阵保留在 diagnostics，权威外松弛是 `bounds/`。

## 运输包与 Q3 筛查

例如将新 replay 的最好时间结构导出为全新代表：

```bash
.venv/bin/python -m src.bench_p1_3b.packages replay_time REPLAY_T01 --rank 0
.venv/bin/python -m src.bench_p1_3b.screen REPLAY_T01 --limit 30
.venv/bin/python -m src.bench_p1_3b.exact_screen REPLAY_T01 --limit 90
```

后两个命令分别冷建任务/站点关系、运行三种分区；可选精确救援只复用同一代表自己已经完成的冷建结果。它们拒绝覆盖原代表的筛查目录。本轮只对 T01 做了一次精确救援，并没有把所有 Q3 结构全面求透。

本轮保存了时间代表 T01/T02/T03（主时间运行 rank 0/1/2），架次 C01/C02、能耗 E01/E02、时效 N01/N02（各 rank 0/1）；重新准入 H_A03/H_A11/H_A12 保证不丢掉更好的已有上界。Q3 冷建代表为 T01、T02、T03、C01、E01、N01。

T01 最初的种子筛查沿用原 helper 的 HiGHS 默认 seed=0，已核对并保存源码；后来所有筛查及精确救援显式 seed=26092511、1 线程。若要逐项复演 T01 初始日志，应使用 diagnostics 中对应源码；它的三个尝试均未输出可行包。

## 权威证据

- `pool_manifest.json`：实际池规模、模式类别、输入和生成器哈希、全模式系数核对。
- `bounds/<目标>/model.npz`、`certificate.json`：全连续时间模式池外松弛及证书。
- `transport_runs/<运行>/model.pbtxt`、`config.json`、`solver.log`：原始 CP 模型、限制和状态。
- `representatives/*.json`、`q2/pareto_schedules/*`：模式副本映射、完整运输包及独立验证。
- `screening/*`：独立冷建、全部失败尝试、任务组目录的局部作用域下界。
- `screening/T01/exact_rescue`：一次精确有限目录救援，完整矩阵和证书。
- `screening/C01/q3/C01/solutions/C01_Q3_001`：已独立验证的 Q3 见证。
- `verification.json`：第二套有理数重算及所有验证产物哈希核验。
- `artifact_manifest.json`：本轮最终新文件清单与 SHA-256；不包含依赖目录、Python 缓存及清单自身。

汇总脚本只读取已明确命名的本轮权威代表/运行；新的 replay 目录不会自动替代正式结论。本轮之后停止，不自动开始分解、列生成、最终 Pareto 或正式主例替换。
