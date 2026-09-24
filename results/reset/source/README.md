# D题求解质量重构：实测反例、研究依据与下一轮任务

审计基准：`chengcongcong222/uav-logistics-comms@badc8a4282f9935018c837e52b32b86539c96071`。

## 最重要的结论

本轮不仅审查代码，也独立建立了一个 Q2 单点往返候选—时间联合整数模型，得到三套零迟到可行方案。没有使用其他参赛者的路线、货箱分组或代码。输入为用户提供的原始工作簿数据和上述提交中的15条 O01→服务区冻结航段；返程按同一水平直线、相同巡航海拔和互换起终点高度计算。

|方案|J_late|J_norm|完工/s|运输能耗/kWh|运输架次|
|---|---:|---:|---:|---:|---:|
|R_FAST|0|0.473919877|6523.487145|67.867219391|26|
|R_BALANCED|0|0.469374030|6878.419578|65.853546500|24|
|R_ENERGY|0|0.526284217|9010.738427|61.495844645|22|

三者在本次试验集合内互不支配；不是原题完整的全局 Pareto 前沿。R_BALANCED 和 R_FAST 在 J_late、J_norm、完工、能耗、架次五个单独指标上，均严格优于仓库旧 P01/P02/P03。R_ENERGY 按核心四目标及原来的词典序及时性也支配旧三点，但其 J_norm 不单独优于所有旧点。

独立检查已覆盖80箱恰好一次、31个硬时限箱、全部80箱期望时间、质量/体积、逐段能耗、返航余量、UAV与电池ID及充电。三套方案均无资源冲突。四种破坏试验（重复箱、负开始时刻、篡改能耗、错误机型资源）均被验证器拒绝。

同一计算口径下的 Q1 校准得到18架次、59.106598393725 kWh，与仓库基准一致。

## 证据边界

- 这是Q2方案，不是Q3方案。尚未为新方案计算通信缺口、中继站点、两架中继及六组件排程。
- 共享的是冻结航段几何；没有重新独立审计DEM穿格。能耗、时间和资源验证为独立实现，未调用本轮优化器的可行标志。
- 当前候选池不完整，只含单点往返。完整等价货箱组合生成732个物理候选，再通过不同机型/目标下的单服务区组合求解和单箱候选构造266个初始模式。这是明确声明的启发式候选池，不是安全支配剔除或完整可行域。
- 搜索的开始时刻使用120/180秒网格，资源占用区间向外取整，属于保守限制；之后保留具体资源顺序进行连续时间左移，再独立复核。该网格不是通信检查步长。
- HiGHS按1%相对间隙容差运行。短时域6600秒试验达到时限并保留约2.51%的受限模型间隙；7200秒约0.863%；9600秒模型间隙为0。这些不是原题的全局最优间隙。
- 日志保留了早期更大模型的限时未得解尝试。不能仅摘录成功求解的短耗时宣称端到端加速倍数。
- 搜索受限时求解和库版本影响，重跑未必得到同一条搜索轨迹。已有执行见证的独立重算不需要重复搜索。
- 尚未写入或推送用户GitHub；先由本地Codex按仓库权威验证器再次交叉验证。

## 文件导航

- `comparison.csv`：旧三点与新三点精确指标。
- `comparison_audit.json`：逐点支配关系，范围仅为显式比较集合。
- `solutions/R_*/`：完整箱组、具体UAV/电池、执行时刻、能耗、逐箱交付、两资源日历、独立审计。
- `solutions/R_*/missions_for_repo_import.json`：用于接入仓库的任务结构，不能直接覆盖旧主结果。
- `q2_search_probe.py`、`q2_search_probe_results.json`：旧搜索代码的四个隔离行为用例，不是完整实例运行。
- `one_stop_probe_solver.py`：本轮自行编写的候选—时段整数模型。
- `left_shift_probe.py`：固定资源序的连续最早开工左移。
- `validate_one_stop_probe.py`：独立物理、逐箱及资源复算。
- `probe_inputs.json`：由用户原始工作簿提取的计算输入；并非网友数据。
- `one_stop_geometry_snapshot.csv`：冻结提交的15条出站航段几何摘录。
- `q1_anchor_crosscheck.json`：Q1计算口径校准。
- `runtime_versions.json`、`manifest_sha256.json`：运行版本与文件哈希。
- `RESEARCH_AND_METHOD_RESET.md`：文献筛选、可借鉴内容和不可迁移的保证。
- `CODEX_NEXT_TASK.md`：目标驱动的求解质量重构任务。

## 复核已存方案

解压后从本目录执行（仅需 Python、NumPy、SciPy；复核脚本本身主要使用标准库）：

```bash
python validate_one_stop_probe.py solutions/R_BALANCED/one_stop_h7200_t180_energy_local_polished_schedule.json
python validate_one_stop_probe.py solutions/R_FAST/one_stop_h6600_t120_energy_local_polished_schedule.json
python validate_one_stop_probe.py solutions/R_ENERGY/one_stop_h9600_t180_energy_local_polished_schedule.json
python q2_search_probe.py
```

重新生成探索结果（会写入当前目录，不覆盖已归档 solutions 子目录）：

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python one_stop_probe_solver.py --pool local --horizon 7200 --step 180 --limit 20 --objective energy
python left_shift_probe.py one_stop_h7200_t180_energy_local_schedule.json
python validate_one_stop_probe.py one_stop_h7200_t180_energy_local_polished_schedule.json
```

Windows可分别设置环境变量或不设置线程变量；无需为此重新安装ns-3。原始XLSX、DEM、第三方库、其他队伍结果均不包含在本包中。
