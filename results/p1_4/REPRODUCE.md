# P1.4 与论文 V0.1 复现

基准提交 `842d950eba19374a287351b9b839fb446ff55d14`，开发分支 `p1-4-fast-frontier-paper`。
WSL Ubuntu-24.04，仓库 `/home/ccc/projects/uav-logistics-comms`。

## 环境

```bash
export PYTHONPATH="$PWD/.deps_p13b:$PWD"
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
```

沿用 `.venv/bin/python` 及 P1.3-B/C 的定版依赖：OR-Tools 9.14.6206、protobuf 6.31.1、absl-py 2.5.0、immutabledict 4.3.1，位于 `.deps_p13b`，不修改原 venv。numpy/scipy等实际版本见 environment.json。

## 本轮实际算法命令

```bash
.venv/bin/python -u -m src.bench_p1_4.search --limit 75
# 运输输出逐步形成，Q3可以在各候选独立验证后单独启动。
for pid in F04 F05 F02 F13 F12 F16; do
  P14_CAP_S=6500 .venv/bin/python -u -m src.bench_p1_4.coupling "$pid" --site-relaxation --iterations 2
done
# 较紧预算发现24架次后，补一次6350秒、24架次的能耗细化。
.venv/bin/python -u -m src.bench_p1_4.refine
for pid in F18 F01; do
  P14_CAP_S=6500 .venv/bin/python -u -m src.bench_p1_4.coupling "$pid" --site-relaxation --iterations 2
done
# F18 的四组合分配反馈：最多三架次必然最多三种(UAV,site)组合。
P14_CAP_S=6500 .venv/bin/python -u -m src.bench_p1_4.coupling F18 --site-relaxation --three-pair-master --iterations 1
.venv/bin/python -m src.bench_p1_4.site_bounds
.venv/bin/python -m src.bench_p1_4.test_models
.venv/bin/python -m src.bench_p1_4.report
.venv/bin/python -m src.bench_p1_4.plot
```

实际执行时部分独立候选并行冷建；每个求解器的 wall、CPU、线程、种子和状态均记录，不把本轮当成等 CPU 比较。4线程CP不保证逐比特复现，候选ID及结果可能变化；重跑应根据 candidate_index.json 选择对应的实际结构，不保证 F13 永远是同一结构。

最初八次Q3筛查的源码保存在 diagnostics/initial_sources/coupling.py，精确重放该版本可将对应 `-m src.bench_p1_4.coupling` 替换为该文件路径。新增三组合约束只用于最后 F18 的 `--three-pair-master` 分支，原失败记录保持不变。

默认结果根为 results/p1_4，已存在求解目录拒绝覆盖。重新运行必须设置例如 `export P14_OUTPUT=results/p1_4_replay`。底层仍读取只读 P1.3-B 模式池及 P1 共享站点；新代表的通信需求和站点关系由本轮冷建，不读取其他结构的候选关系。

report.py 是权威目录的汇总与审计入口，要求完整候选索引、历史保护快照和已完成的论文文件；改变目录的探索重跑应先按新任务范围建立保护快照。独立执行核验由每次 save_answer 自动调用原 mathematical/reset_q3_validate 流程，原验证结果与产物 SHA-256 随执行包保存。

## 模型与目标域

1. Q2：完整既有2903模式池、所有类允许的副本、0.1秒保守区间、J_late=0、原资源，先最小运输架次，再固定已找到架次数最小运输能耗。不是已证明的字典序全局最优。
2. Q3：固定该运输结构、自由开始时刻及同型资源次序，采用P1.3-C站点/中继机一致性松弛。联合完工编码上限6500秒，子问题显式总中继架次数不超过3。
3. 固定时刻动态列依次求完整覆盖、架次和有限目录中继能耗。能耗采用1e6缩放整数系数，真实能耗由原物理模型核验。可用站点、资源数量和Gamma不变。
4. 全部已验证执行包依据实际联合时间，统一归入6155/6250/6350/6500四档。较紧预算的方案自动参与较松预算的比较，避免把独立限时运行的优劣误当作可行域非单调。
5. 下界/gap仅在各自声明的编码域有效。不可将保守网格时间下界转给连续物理指标；超时或网格模型无解不等于原连续Q3不可行。

## 证据入口

- protocol.json：场景、真实预算百分比、资源和优先顺序。
- transport_runs/：9个运输优化模型、日志、原始状态、候选轨迹。
- representatives/、q2/：19套本轮独立验证运输包，包括明确标记的历史同结构候选。
- screening/：8个结构的冷通信关系、联合主问题、生成列、成功/失败和完整Q3包。
- independent_audit.json：Q2/Q3哈希与矩阵原始解复核。
- epsilon_budget_results.json：各预算内最好已知方案。
- validated_archive.json、near_fast_frontier.json：有限档案及五维非支配关系；不声称完整前沿。
- recommended_tradeoff.json：阶段性主候选建议，不改正式主例。
- GPT_SYNC.md、PAPER_RESULTS_ADDENDUM.md：完整反馈及正文的独立结果补充。
- figures/near_fast_tradeoffs.*：可复建标准图。
- protection_check.json、artifact_manifest.json：历史保护和本轮产物封存。

论文正文及冻结数据在 results/paper_v01/，构建命令见该目录 REPRODUCE.md。V0.1冻结于P1.3-C；P1.4补充未悄悄写入旧冻结正文。Q4重算、正式主例和工作簿替换、G2 Q1余量敏感性及文献排版留在明确的后续清单。
