# P1.3-C 复现

工作目录：`/home/ccc/projects/uav-logistics-comms`，WSL Ubuntu-24.04。
基准：`f150743dea36d655204e74372580f98ebd9a8cf8`。
开发分支：`p1-3c-fast-q3-rescue`。

## 环境

沿用原 `.venv/bin/python`，附加依赖位于 `.deps_p13b`，不修改原 venv。精确版本见 environment.json。依赖目录缺失时：

```bash
.venv/bin/python -m pip install --target .deps_p13b --no-deps \
  ortools==9.14.6206 protobuf==6.31.1 absl-py==2.5.0 immutabledict==4.3.1
export PYTHONPATH="$PWD/.deps_p13b:$PWD"
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
```

CP 运输主问题为 4 线程，列主问题为 1 线程，开发种子 26092511。多线程求解不保证逐比特复现，达到的并列时刻或后续结构可能不同；禁止覆盖当前权威结果。

## 重放检查（不重新求解）

```bash
.venv/bin/python -m src.bench_p1_3c.test_models
.venv/bin/python -m src.bench_p1_3c.verify
```

tests：两个站点覆盖冲突及高阶冲突、资源区间端点复用、站点列支配保留资源权衡、120 余列的精确能量与原构造器交叉核对。
verify：原始站点掩码下界、独立占用冲突复算、矩阵整数原始解、4 套独立执行包的验证结果与哈希。验证器只写本阶段验证汇总，不改动执行包。

## 在新结果目录重跑开发试验

```bash
export P13C_OUTPUT=results/p1_3c_replay
mkdir -p "$P13C_OUTPUT"
# T01 初始固定时刻运行实际使用的未剪枝 SciPy/HiGHS 源码已保存。
.venv/bin/python results/p1_3c/diagnostics/initial_sources/fixed.py T01 --rounds 3 --limit 20
# 此后采用安全同任务集合支配剪枝和 CP-SAT 列选择。
.venv/bin/python -m src.bench_p1_3c.coupling T01 --iterations 6
.venv/bin/python -m src.bench_p1_3c.coupling T01 --site-relaxation --iterations 3
for pid in T02 T03; do
  .venv/bin/python -m src.bench_p1_3c.fixed "$pid" --rounds 2 --limit 20
  .venv/bin/python -m src.bench_p1_3c.coupling "$pid" --site-relaxation --iterations 3
done
.venv/bin/python -m src.bench_p1_3c.verify
unset P13C_OUTPUT
```

`common.py` 对输出根目录提供 P13C_OUTPUT 入口，求解阶段拒绝覆盖同名运行目录。没有指定时写 results/p1_3c。每个代表复用的仅是其自身 P1.3-B 冷建原子任务与全部 118 站点关系；输入哈希在各自 input_reuse.json。禁止以本轮运行做“统一冷启动/等 CPU”比较。

初始固定 T01 的 SciPy 运行、cut-only 分解、最终站点一致性分解均保留，不删除限时或失败结果。诊断源快照与最终源文件一起提交；不是只有最佳执行包。

## 文件导航

- GPT_SYNC.md：完整解释、结果、局限和下一阶段边界。
- gate.json：正式 Gate；本轮完成后停止。
- relay_mode_manifest.json：每次动态模式目录及哈希。
- fixed_T01_results.json、fixed_timing_comparison.json：固定时刻结果和冲突。
- decomposition_log.json：有效反馈、启发式排除与成功循环。
- T01_T02_T03_comparison.json：4 套执行包及调度位移。
- solver_bounds.json、bound_transfer_audit.json：原始域内 bound/gap 与禁止跨域转用说明。
- full_site_relay_bounds.json：不依赖生成目录的 3 架次下界。
- independent_audit.json、conflict_certificate_replay.json：独立核验汇总。
- MODEL.md：模型域、必要性推导与限制。
- artifact_manifest.json：最终源代码及成果哈希。

完整包路径形如 `results/p1_3c/T01/q3/T01/solutions/T01_C2_SITE_RELAY_00_Q3/`。每个包含运输/中继日历、全航程轨迹、物资交付、能耗、通信保障、验证结果及输入哈希。原独立验证实际由 `src.bench_p1_2.driver.audit` 调用 `validation/mathematical/reset_q3_validate.py`，所有成功包已调用该流程；0.5 s 全航程采样附加阶段/间隙边界和 0.1 s 边界细化。

不运行正式种子，不替换主例、Q4、工作簿或旧论文结论。
