#!/usr/bin/env python3
"""Generate the E52 engineering report and GPT handoff from audited artifacts."""
from pathlib import Path
import hashlib
import json
import sys

import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
Q3=ROOT/'results/q3'


def main():
    meta=json.loads((Q3/'e52_run_meta.json').read_text())
    val=json.loads((Q3/'e52_rescue/validation.json').read_text())
    fine=json.loads((Q3/'e52_rescue/sampling_sensitivity.json').read_text())
    assert val['gate']=='E5_Q3_RELAY_TASKS_READY'
    assert fine['violations']==0
    assert val['fingerprint']==meta['fingerprint']
    for file,h in val['output_sha256'].items():
        assert hashlib.sha256((Q3/file).read_bytes()).hexdigest()==h,file
    assert fine['candidate_sha256']==val['output_sha256']['relay_task_candidates_e52.csv']
    pairs=pd.read_csv(Q3/'relay_task_candidates_e52.csv')
    atoms=pd.read_csv(Q3/'relay_atomic_tasks_e52.csv')
    events=pd.DataFrame(json.loads((Q3/'e52_rescue/progress_events.json').read_text()))
    st=meta['stats']
    access_rate=st['access_cache_hits']/(st['access_cache_hits']+st['access_los_calls'])
    rg_rate=st['rg_cache_hits']/(st['rg_cache_hits']+st['rg_los_calls'])
    rows=[]
    for r in meta['summary']:
        pid=r['pareto_id']; p=pairs[pairs.pareto_id==pid]
        rows.append(f"| {pid} | {r['parent_gaps']} | {r['atomic_tasks']} | {r['candidate_pairs']} | {r['sites']} | {p.min_twohop_margin_db.min():.6f} | {r['separate_mission_min_energy_sum_kwh']:.6f} |")
    table='\n'.join(rows)
    report=f'''# E5.2 — Lazy relay feasibility and independent audit

## Decision

```text
E52_FEASIBILITY_RESOLVED
E52_RELAY_CANDIDATES_VALID
E52_RELAY_ENERGY_VALID
E52_ATOMIC_TASKS_VALID
E52_QUARTER_SECOND_CHECK_VALID
E5_Q3_RELAY_TASKS_READY
```

**E6 has not started.** READY means a validated relay-site witness exists for
every atomic interval. It does not mean that two relay UAVs and six energy
components can already execute these intervals jointly.

`candidate_set_complete = false`; `generation_mode = LAZY_FEASIBILITY_FIRST`.
The authoritative gate is `e52_rescue/validation.json`, bound to artifact hashes.
The generator's `PENDING_INDEPENDENT_VALIDATION` field records its status before
the separate audit; it is not an additional unresolved scientific gate.

## Final canonical results

| Plan | Parent gaps | Atomic tasks | Candidate pairs | Sites within plan | Min two-hop margin/dB | Separate-mission min-energy sum/kWh |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
{table}

- Global: **78 parent gaps, 78 atomic tasks, 126 candidate pairs, 68 unique sites,
  zero unresolved intervals**. Site counts overlap between plans.
- Every original gap now has a whole-gap fixed-site witness. No split gaps
  remain. Thus one task per gap is minimal within the fixed parent-gap setup;
  this does not optimize merging across different parents.
- Candidate counts: 48 tasks have one site, 12 have two, and 18 have three.
- All 78 tasks, and all 126 retained pairs, have zero individually required
  transport shift. This does not include fleet/resource conflicts.
- Minimum energy margin over all retained pairs:
  **{pairs.energy_margin_kwh.min():.6f} kWh**.
- Minimum two-hop margin is **{pairs.min_twohop_margin_db.min():.6f} dB**;
  the tightest limit is the backhaul. Minimum access margin is
  **{pairs.min_access_margin_db.min():.6f} dB**. These witnesses have no guaranteed
  additional 2/4/6 dB robustness budget.
- Energy sums in the table concern separate missions using retained candidates.
  They are **not a proven lower bound on E6 energy**: task merging can save
  repeated travel/setup, and lazy pools may omit lower-energy sites.

## What changed and why the old result was unreliable

1. Corrected necessary bbox intersection extrema, including in archived E5.1.
2. Removed cross-sortie interpolation from the active E52 path. Trajectories now
   come from canonical P01–P03 trace packages, keyed by plan and sortie, with
   bracketing phase points retained.
3. Use vectorized distance gates, cached static backhaul/geometry and identified
   access samples; verify dense intervals only after sparse checks pass.
4. Use old candidate/site tables only as warm starts. Generate separate `_e52`
   canonical tables; do not overwrite legacy tables or append unverified rows.
5. Preserve endpoints/phase/handover boundaries and use <=0.5 s sampling with
   observed LOS transition refinement <=0.1 s. Independent audit reconstructs
   every retained pair and energy from inputs, not stored energy summands.
6. Checkpoint after each atom/parent; bind resume to code/config/input hashes,
   including the DEM file. Static caches persist; access caches are in-memory.

The bbox correction alone should not receive all performance credit. On the 78
correctly isolated parent trajectories, old/new necessary-box area ratios range
from 1.053 to 2.463, median 1.258. This is not an ablation timing experiment.
Lazy existence search, corrected trajectory identity and cached computation all
contribute. No isolated causal speedup factor is claimed.

## Rescue provenance

The historical “8 unresolved parents” are actually **8 unresolved old atoms in
5 distinct parent gaps**.

| Event category before merge-back | Count |
| --- | ---: |
| Old resolved atoms presented for revalidation | 84 |
| Revalidated using selected old candidates (at most 3 tried) | 37 |
| Other old resolved atoms rescued using site library | 44 |
| Other old resolved atoms rescued by new 120 m grid | 3 |
| Old unresolved atoms | 8 |
| <=30 s pieces made from those 8 atoms | 42 |
| Those pieces rescued using existing library | 42 |
| Deeper split operations | 0 |
| 60/30 m grid rescue, local 5 m rescue, continuous rescue | 0 |
| Total successful search jobs before merge-back | 126 |
| Successful adjacent merge-back operations | 48 |

Failure of the selected three warm candidates does not prove an old task
infeasible. It demonstrates why old candidate tables cannot be accepted without
revalidation. The three new-grid rescues were P01 G000/A02, G003/A00 and G007/A00;
later plans could reuse these newly cached sites.

The 8 formerly unresolved atoms did not need exhaustive 30 m / 25 m search or
continuous optimization. The <=30 s split was a construction device; successful
merge-back eventually supplied a witness for each original full gap.

## Measured computation

| Metric | Measured value |
| --- | ---: |
| Cheap candidate/interval attempts, including repeat attempts | {st['cheap_candidates_examined']} |
| After vectorized range gates | {st['after_distance_candidates']} |
| Sparse interval checks | {st['sparse_interval_checks']} |
| Dense interval checks, including revalidation/merge-back | {st['exact_interval_checks']} |
| Actual T–R LOS calls | {st['access_los_calls']} |
| Actual R–G LOS calls | {st['rg_los_calls']} |
| Access cache hits / hit rate | {st['access_cache_hits']} / {access_rate:.2%} |
| R–G cache hits / hit rate | {st['rg_cache_hits']} / {rg_rate:.2%} |
| Static flight-geometry calculations | {st['static_geometry_computations']} |
| Static geometry cache hits | {st['static_geometry_cache_hits']} |
| Generation + merge-back, resumed run | {meta['runtime_s']:.3f} s |
| Independent 0.5 s candidate/energy/coverage audit | {val['runtime_s']:.3f} s |
| Additional all-pair 0.25 s audit | {fine['runtime_s']:.3f} s |

One worker; OMP/MKL/OpenBLAS thread limits = 1. Runtime excludes interpreter/
initial input loading and is not the full engineering-turn duration. Search
counts include provisional and merged candidates, not just final retained pairs.
Old exhaustive-run LOS counts and completed runtime do not exist; no numerical
before/after speedup ratio or complete feasible-site retention rate is reported.

## Validation and reproducibility evidence

- All 126 final pairs independently checked; 68 site legality/backhaul checks.
- Independent 0.5 s audit: {val['access_samples']} access samples and
  {val['boundary_refinement_samples']} transition refinement samples.
- Additional 0.25 s audit: **{fine['all_pairs_checked']} pairs, 0 violations**,
  {fine['samples']} access samples. Maximum absolute access-minimum change versus
  the stored 0.5 s result: {fine['maximum_absolute_margin_difference_db']:.3g} dB.
- All 78 E4 parent gaps covered exactly within numerical tolerance, without
  holes or overlaps, with positive duration and >=1 candidate per task.
- Final adjacent-union checks = 0 because every parent already has one task.
  Generation performed 48 verified merge-back operations.
- 10 targeted regressions passed: intersection/diameter necessity, no unsafe
  geometric exclusions, sortie isolation, phase endpoints, no extrapolation,
  dense/refined outage rejection, task-aware caches, energy-duration update,
  and scientific-input fingerprint coverage.
- Controlled stop after 3 jobs, followed by resume, completed all 126 jobs;
  changed-code stale checkpoint was explicitly rejected. Pilot and final
  canonical table hashes agree, despite the intervening persistence hardening.
- Raw-data and repository hygiene checks are rerun before publication. Existing
  unrelated Q2 working-tree changes and the missing legacy E5 gate-stat CSV
  remain untouched; only E52-related paths are committed.

Numerical sampling remains a finite-resolution test, **not an analytic proof of
continuous-time connectivity**. The primary frozen DEM LOS primitive is reused;
the independent validator independently reconstructs its inputs and propagation
arithmetic. The 0.25 s audit tests time-resolution sensitivity, not a different
terrain-occlusion model.

## Artifacts and reproduction

- `src/q3/e52_geometry.py`, `src/q3/e52_lazy.py`
- `validation/mathematical/e52_validate_candidates.py`
- `validation/mathematical/e52_sampling_sensitivity.py`
- `validation/mathematical/e52_test_regressions.py`
- `docs/model/Q3_RELAY_E52_SEMANTICS.md`
- `relay_atomic_tasks_e52.csv`, `relay_task_candidates_e52.csv`, `relay_sites_e52.csv`,
  `relay_unresolved_e52.csv`, `e52_run_meta.json`
- `e52_rescue/checkpoint.json`, `resolved_atoms.csv`, `candidate_sites.csv`,
  `progress_events.json`, independent audit CSVs, validation and sensitivity JSONs.

```bash
cd /home/ccc/projects/uav-logistics-comms
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
.venv/bin/python -m src.q3.e52_lazy --resume
.venv/bin/python validation/mathematical/e52_validate_candidates.py
.venv/bin/python validation/mathematical/e52_sampling_sensitivity.py
.venv/bin/python validation/mathematical/e52_test_regressions.py
.venv/bin/python environment/e52_report.py
```

On a fresh output directory omit `--resume`. Preserve the old checkpoint before
a clean rebuild; never bypass a fingerprint mismatch. Input data and the Python
environment are local dependencies and remain outside version control.

## Next handoff boundary

Stop at E5.2. E6 may consume the new tables to examine task overlap, shared-site
merging, two relay UAVs and six independently charged energy components. It must
not mistake zero per-task shift for fleet-feasible zero shift. With 48 singleton
candidate pools and narrow margins, targeted candidate expansion may be needed.

Do not rerun Q2 or modify its objective/physics merely to accommodate this
candidate generator. Use the canonical E3.2 P01–P03 packages; legacy top-level Q2
objectives and schedules were already inconsistent before this change.
'''
    (Q3/'E52_REPORT.md').write_text(report,encoding='utf-8')
    sync=f'''# E5.2 前线同步

结论：**E5_Q3_RELAY_TASKS_READY**。E6 尚未执行。

本轮接受“惰性可行性搜索”方向，并补上逐架次轨迹重建、完整边界采样、
带输入/代码/参数指纹的断点续跑，以及所有最终候选的独立物理复算。
候选池仍明确为 `candidate_set_complete=false`，不声称完整枚举或最优性。

| 方案 | 原始 gap | 最终任务 | 候选对 | 方案内站点 | 最小双跳余量/dB | 独立架次最小能耗和/kWh |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
{table}

全局 78 个任务、126 个候选对、68 个站点、0 个未解；每个原始 gap 都有
单个固定站点完整覆盖的见证。能耗和仅是当前候选池下独立架次指标，不是
允许任务合并后的全局能耗下界。

关键情报：

1. 原先的 8 个未解对象是 **8 个 atom，归属 5 个 parent gap**。先拆成 42 个
   不超过 30 秒的片段，全由旧站点库救回；最后 merge-back 消除了所有分段。
2. 旧称已解决的 84 个任务，优先挑出的最多 3 个旧候选只有 37 个任务复核通过。
   其余 44 个由站点库救回，3 个由新 120 m 网格救回。没有使用更细网格或连续救援。
3. 根因不只是 bbox。E5.1 把同时间段不同 sortie 混合插值，这会直接扭曲轨迹。
   E52 从规范 trace 按 `(pareto_id,sortie_id)` 重建。bbox 修正有益，但不能把
   全部加速归因于它；没有做控制变量性能归因实验。
4. 单进程生成及合并约 **{meta['runtime_s']:.2f} 秒**；独立全量验证约
   **{val['runtime_s']:.2f} 秒**；额外 0.25 秒采样全量复核约 **{fine['runtime_s']:.2f} 秒**。
   旧暴力运行没有可靠计数，故不报告虚构的倍数加速或完整可行域收缩率。
5. 所有候选的单任务 `required_transport_shift=0`，但尚未施加两架中继、六个
   能源组件的共享资源约束，不能解释为联合排程已经可行。
6. 最小双跳余量约 **{pairs.min_twohop_margin_db.min():.6f} dB**，瓶颈为回传；
   48 个任务仅保留 1 个候选。E6 可能需要按冲突任务定向扩展候选，E8 鲁棒预算
   更不能直接从当前可行性通过推断。0.25 秒复核无新增失联，但这仍是数值验证。

验证：`E52_RELAY_CANDIDATES_VALID`、`E52_RELAY_ENERGY_VALID`、
`E52_ATOMIC_TASKS_VALID` 全通过；0.25 秒 126 对全量复核零失败；10 个回归测试通过。
断点在第 3 个任务后停止并恢复成功，失效代码指纹拒绝续跑；正式输出与试跑输出
哈希一致。没有启动 E6、ns-3 正式场景或 Q4。

权威文件：同目录 `E52_REPORT.md`、`e52_run_meta.json`、四个 `*_e52.csv`，
以及 `e52_rescue/validation.json`。生成器元数据的 PENDING 字段是提交验证前
的阶段状态；最终 Gate 请读独立验证 JSON。旧 E5 表仅为 warm start，旧统计不恢复
为论文证据。E3.2 规范 P01–P03 包保持不变，旧顶层 Q2 文件口径混杂问题另行保留。

下一步允许准备 E6 中继合并/资源调度，但本轮到此停止。
'''
    (Q3/'E52_GPT_SYNC.md').write_text(sync,encoding='utf-8')
    print('E52_REPORTS_GENERATED')


if __name__=='__main__':main()
