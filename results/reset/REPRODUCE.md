# G2 复核与重算入口

在 WSL Ubuntu-24.04 的 `/home/ccc/projects/uav-logistics-comms`，使用仓库 `.venv`。

```bash
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
.venv/bin/python validation/mathematical/reset_gate.py
.venv/bin/python validation/mathematical/test_reset_regressions.py
.venv/bin/python validation/mathematical/test_xb1_regressions.py
```

Gate 核对已有独立证据及输入/产物哈希，不重新搜索。可分别重算独立检查：

```bash
.venv/bin/python validation/mathematical/reset_q1_validate.py
.venv/bin/python validation/mathematical/reset_q3_validate.py A11
.venv/bin/python validation/mathematical/reset_q4_validate.py
.venv/bin/python validation/mathematical/reset_submission_validate.py
```

带运行时间的审计 JSON 重写后会改变哈希。复核应在独立检出/结果副本中运行；如果有意重做正式证据，按 Q3 → Q4输入清单 → 提交输入清单 → Gate 的顺序刷新，不能只改下游通过标记。细审计支持 `--step .25`，该命令会检查指定运输结构下全部导出点。

从原始数据重建的核心命令如下；新的实验应使用新目录/ID，不覆盖本轮归档。

```bash
.venv/bin/python -m src.reset.import_audit
.venv/bin/python -m src.reset.geometry
.venv/bin/python validation/mathematical/reset_geometry_validate.py
.venv/bin/python -m src.reset.q1
.venv/bin/python -m src.reset.patterns --build
.venv/bin/python -m src.reset.patterns --pid A11 --horizon 6600 --step 120 --limit 60 --single
.venv/bin/python -m src.reset.patterns --pid A12 --horizon 7200 --step 180 --limit 60 --single
.venv/bin/python -m src.reset.patterns --pid A03 --horizon 9600 --step 180 --limit 60
.venv/bin/python -m src.reset.patterns --pid AS01 --horizon 12000 --step 180 --limit 60 --soft
.venv/bin/python -m src.reset.q3 A11
.venv/bin/python -m src.reset.q3 A03
.venv/bin/python -m src.reset.reconstruct A11
.venv/bin/python -m src.reset.challenges q2
.venv/bin/python -m src.reset.challenges q3
.venv/bin/python -m src.reset.cell_challenge
```

模式选择与时间上限依赖求解器/运行环境；这些命令是实际运行配置，不承诺限时重跑逐字节同解。`controls.py` 的 `external('run01','B01')` / `external('run02','B02')` 单独生成带来源外部对照，`lns(60)` 是均匀算子基线。A01/A02 无见证的失败运行也有日志，不能从预算统计中删去。

所有 Q2 执行包先用 `xb1_validate.check_package(path,pid,G2_geometry_dataframe)` 核对。该独立算术检查器沿用历史名称；本轮几何由显式参数指定，正式版本与输入哈希由 G2 Gate 再绑定。AN01 的 Q2 目录只是开始为零的相对结构模板，不能作为 Q2 可执行答案；只有其 Q3 完整执行包接受验证。

Q3 完整结果通过后，运行：

```bash
.venv/bin/python -m src.reset.q4
.venv/bin/python -m src.reset.q4_report
.venv/bin/python validation/mathematical/reset_q4_validate.py
.venv/bin/python -m src.reset.submission
.venv/bin/python validation/mathematical/reset_submission_validate.py
.venv/bin/python -m src.reset.report
.venv/bin/python validation/mathematical/reset_gate.py
```

正式 Q3 主例在新 Q4 和提交模块中显式固定为 A11_Q3_001。换代表时必须同步修改该配置、独立验证器及源哈希，并重新计算依赖块；不能只替换报告中的编号。
