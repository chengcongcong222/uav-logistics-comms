"""Assemble P1.3-C handoff from recorded results; no optimization."""
import platform,subprocess,sys
from pathlib import Path
from src.bench_p1_3c.common import *

def main():
    independent=read(OUT/'independent_audit.json');proofs=read(OUT/'conflict_certificate_replay.json');bounds=read(OUT/'full_site_relay_bounds.json')
    comparisons=[];fixed=[];decomposition=[];modes=[];solver=[]
    for pid in ['T01','T02','T03']:
        base=ROOT/'results/p1_3b/representatives'/f'{pid}.json'
        stages=sorted((OUT/pid).glob('C*/result.json'))
        for p in stages:
            r=read(p)
            if p.parent.name=='C1_FIXED':fixed.append(dict(pid=pid,path=str(p.relative_to(ROOT)),result=r,
                fixed_time_conflict_certificates=[c for c in proofs if c['stage']=='fixed' and '/'+pid+'/' in c['source']]))
            if p.parent.name in ['C2','C2_SITE']:decomposition.append(dict(pid=pid,stage=p.parent.name,result=r))
            columns=p.parent/'columns.json'
            if columns.exists():
                rows=read(columns)
                modes.append(dict(pid=pid,stage=p.parent.name,path=str(columns.relative_to(ROOT)),sha256=digest(columns),generated_modes=len(rows),
                    unique_task_groups=len({tuple(c['task_ids']) for c in rows}),represented_sites=len({c['site_id'] for c in rows}),
                    master_columns=[i['columns'] for i in r['iterations']],heuristic_pricing=True,
                    exact_fields=['tasks','site','endpoint_order','outbound/return time','service interval','union energy','UAV occupation','component occupation']))
        packages=[a for a in independent['packages'] if a['pid']==pid]
        rows=[]
        for a in packages:
            w=read(ROOT/a['package']/'witness.json');shifts=w['shifts']
            rows.append(dict(package=a['package'],id=Path(a['package']).name,metrics=w['metrics'],
                fixed_transport_timing=all(v==0 for v in shifts.values()),minimum_shift_s=min(shifts.values()),maximum_shift_s=max(shifts.values()),
                relay_lower_bound=3,relay_upper_bound=w['metrics']['relay_sorties'],relay_count_gap=0,
                relay_bound_scope='All 118 frozen site/task relations; fixed transport structure; unsplit atoms. Not all Q3 structures or arbitrary handover.',
                independent_validation_sha256=a['validation_sha256']))
        comparisons.append(dict(pid=pid,q2_baseline=read(base),Q3_closed=bool(rows),witnesses=rows))
    for p in sorted(OUT.glob('*/C*/**/result.json')):
        r=read(p)
        if 'incumbent' not in r:continue
        solver.append(dict(path=str(p.relative_to(ROOT)),**r))
    write(OUT/'relay_mode_manifest.json',dict(coordinates=118,Gamma_C_db=0,relay_uavs=2,energy_components=6,source='Same-structure P1.3-B cold templates/edges, hash-bound reuse',
        mechanism='Singleton restricted master -> site/time-window columns -> task-dual-guided subsets; C2 site/UAV relaxation supplies additional groups.',
        pricing='HEURISTIC_DYNAMIC_GENERATION_NOT_PROVEN_COMPLETE_COLUMN_GENERATION',safe_pruning='Only same-task-set columns dominated in all resource endpoints, return time and energy are removed.',catalogues=modes))
    write(OUT/'fixed_T01_results.json',next(r for r in fixed if r['pid']=='T01'))
    write(OUT/'fixed_timing_comparison.json',fixed)
    write(OUT/'decomposition_log.json',dict(stages=decomposition,valid_cut_rule='Never generated from a timeout; exhaustive two-site coverage failure of mandatory-occupation overlap only.',
        heuristic_exclusions='Two 30-second timing-box diversification exclusions in the cut-only T01 diagnostic; not infeasibility cuts and not present in the successful C2_SITE runs.'))
    write(OUT/'T01_T02_T03_comparison.json',comparisons)
    write(OUT/'solver_bounds.json',dict(finite_subproblems=solver,all_site_relay_count_bounds=bounds,continuous_bound_transfer=read(OUT/'bound_transfer_audit.json'),
        full_continuous_joint_makespan_optimality_proven=False,raw_solver_gap_is_domain_specific=True,
        timing_note='Per-solve CPU and wall are recorded. Relay-stage cpu_s ends before independent validation; validator runtime is separate. No equal-CPU algorithm comparison.'))
    gate=dict(status='P1_3C_FAST_Q3_CLOSED',base_commit=BASE,branch='p1-3c-fast-q3-rescue',verified_structures=['T01','T02','T03'],verified_packages=len(independent['packages']),
        hard_layer_J_late_max=1e-4,all_witnesses_J_late=0.,Gamma_C_db=0,relay_uavs=2,energy_components=6,
        transport_structure_changed=False,fixed_T03_closed=True,fixed_T01_closed=False,
        fixed_T01_conflict_scope='Proven only within frozen 118-site unsplit guarded atom service domain; not arbitrary handover or analytic full-physics infeasibility.',
        certified_relay_sorties=3,relay_count_claim_scope='Each of the three fixed transport structures, frozen site/task relation, unsplit atoms, arbitrary timings.',
        global_Q3_makespan_optimality_proven=False,pricing_complete=False,formal_algorithm_comparison=False,final_pareto_front_generated=False,
        official_example_Q4_submission_replaced=False,stop_after_this_phase=True)
    write(OUT/'gate.json',gate)
    old=read(OUT/'protected_files.json');changed=[p for p,h in old.items() if not (ROOT/p).is_file() or digest(ROOT/p)!=h]
    assert not changed,changed[:10]
    main_hash=subprocess.check_output(['git','rev-parse','main'],cwd=ROOT,text=True).strip();assert main_hash=='c13306ecbc36933502d1197228e5d80f9f7e40cf'
    write(OUT/'protection_check.json',dict(status='PASSED',files=len(old),changed=changed,main=main_hash))
    import numpy,scipy,ortools,google.protobuf,pandas
    write(OUT/'environment.json',dict(python=sys.version,platform=platform.platform(),numpy=numpy.__version__,scipy=scipy.__version__,pandas=pandas.__version__,
        ortools=ortools.__version__,protobuf=google.protobuf.__version__,development_seed=26092511,CP_master_workers=4,CP_column_workers=1,
        BLAS_threads=1,base_commit=BASE,dependencies_target='.deps_p13b',bitwise_reproducibility_not_claimed=True))
    table=[]
    for r in comparisons:
        for w in r['witnesses']:
            m=w['metrics'];label='固定原时刻' if w['fixed_transport_timing'] else '释放时刻/资源次序'
            table.append(f"| {r['pid']} | {label} | {m['joint_makespan_s']:.6f} | {m['joint_makespan_s']/60:.4f} | {m['total_energy_kwh']:.6f} | {m['J_norm']:.9f} | 27 + 3 |")
    body='''# P1.3-C：快速运输结构的 Q3 耦合救援

**Gate：`P1_3C_FAST_Q3_CLOSED`。T01、T02、T03 均得到独立验证的零迟到 Q3 见证，共 4 套。**

基于 `f150743dea36d655204e74372580f98ebd9a8cf8`，开发分支 `p1-3c-fast-q3-rescue`。本轮没有改变三个运输结构的箱组、访问顺序、机型和 27 架次；没有扩展运输模式池，没有读取外部解结构，没有运行正式算法比较。Gamma=0、118 个冻结站点、2 架中继、6 个能源组件不变。

## 1. 实际通过验证的结果

| 结构 | 调度自由度 | Q3 联合完工 s | 分钟 | 总能耗 kWh | J_norm | 运输 + 中继 |
|---|---|---:|---:|---:|---:|---:|
TABLE

四套方案的 J_late 均为 0。T01 原 Q2 完工 6101.161066593 s、T02 原 Q2 6130.112084592 s、T03 原 Q2 6210.023650112 s 仍是原运输基线；表内为新 Q3 完工，不混用二者。

T01 与 T02 的联合完工只差约 0.0033 s，小于通信核验采样尺度，不强调这点数值差异。T01 的 J_norm 更好；T02 能耗更低。T03 调整后能耗进一步下降，但时间较长。T03 固定时刻方案的 J_norm 比其重排方案更好。这里保留实际权衡，不生成最终 Pareto 前沿，也不预指定某个方案替换正式主例。

## 2. 固定 T01 为什么不闭合：有作用域明确的冲突证据

T01 的固定时刻动态目录从 1336 个可行单任务/站点模式扩至 11948 个模式。初始 SciPy/HiGHS 运行仍存在限时没有 incumbent 的情况，这些失败运行全部保留。

另外独立发现了与求解超时无关的必要占用冲突。例如任务 T01_M005_G00、T01_M007_G00、T01_M019_G00 两两没有共同可行站点，计入各自最短准备、出航、返航和周转后，其必需中继占用区间在 [4030.470561, 4115.803610] s 相交，长约 85.333 s。三个不同的保障架次此时至少占用三架中继，而资源只有两架。

这个证书严格限定在“冻结 118 站点及其任务—站点关系、每个带保护边界的原子任务完整交给一个固定站点架次”的域。它不证明允许原子任务内部交接、改变站点集合或精确连续无线重构后的物理问题不可行。T02 固定时刻也有同类证据。T03 没有该证书，而且动态模式已经找到固定时刻可行解。

证书公式、原始系数、任务集合与复算见 MODEL.md、initial_conflict_diagnostic.json（T01）及 conflict_certificate_replay.json。正式分解用可复核的非重叠析取约束反馈运输主问题；没有把 solver time limit 变成不可行 cut。

## 3. 真正奏效的算法改变

C1 的 restricted master 精确选择已生成列，覆盖每个原子任务一次，并在所有相关开始事件处限制中继占用不超过 2、能源组件占用不超过 6。时间固定后，这类区间容量条件可以恢复完整资源编号。中继列保存覆盖任务、站点、端点顺序、出返航、服务区间、区间并集通信能耗、无人机占用和组件占用。

模式从单任务开始，按站点—时间窗生成组合，再用 LP 任务对偶值生成子集。这是启发式动态模式生成，没有完整 pricing 证明。相同任务集合下，只移除准备更早、资源释放更晚等各项均不优的站点列；所有原始生成列仍归档。

T01 第一轮只用占用冲突 cut 的分解虽改善了时刻，有限模式主问题仍留下一个任务，主要是 M007。随后加入更强的站点/中继机一致性松弛：为每个原子任务选择站点和中继机；同一中继机若在两个不同站点保障任务，必须允许出返航和周转后的完整占用区间错开；同站点任务暂允许共享一个尚未检查能量的长架次。运输无人机、电池次序也自由。

这一松弛仍未替代完整 Q3，它暂忽略中继电量与组件日历。但它生成的任务—站点组合反馈给动态中继主问题后，三个结构都在第一轮得到 3 架次完整方案；原始精确区间并集能耗、分段充电函数和独立验证全部通过。成功来自一致的站点分配与联合调度，而非简单把旧 115 模式 MILP 延长时间。

第一轮 cut-only 诊断还用过两个 30 秒时刻盒排除作启发式多样化，均明确标注不是不可行 cut；成功的 C2_SITE 三次运行没有使用这些排除。

## 4. 不是“小幅挪动”：时刻重排应如实解释

T01 相对原 Q2 时刻的最大提前为 3623.5 s，最大推迟 2292.6 s，绝对时移总和 25086.2 s。T02 同样发生较大重排。任务结构完全不变，但同型无人机和电池资源次序允许重排。因此可以说“固定运输结构下联合重排救援成功”，不能写成“只延迟几分钟就解决了通信”。

T03 固定时刻分支则真正保持所有运输开始时刻及原资源分配不变，3 中继方案已验证；为改善其 6443.030006 s 联合完工，又运行同一自由调度机制，得到 6210.023650 s。

## 5. 哪些最优性可以说，哪些不能说

对每个结构，分别穷尽全部冻结站点的两站点覆盖掩码组合：T01 有 39 种不同掩码、780 种可重复二组合；T02/T03 各有 38 种、741 种。没有任何两个站点覆盖全部原子任务，因此任意符合该原子服务域的完整方案至少需要 3 个中继架次。当前三个结构均已有独立验证的 3 架次解，故**在各自固定运输结构、冻结任务—站点关系和原子任务不拆分的域内，中继架次数下界=上界=3**。这个证书不再只依赖此前的 115 个分组目录，也不是整个 Q3 所有运输结构的全局最优性证明。

运输主问题使用保守 0.1 s 网格，准备/飞行/占用系数向安全方向取整，零迟到用严格 J_late=0。它的编码目标最优值分别为 6154.0、6154.0、6210.1 s。它们比对应实际连续时间执行指标高约 0.10/0.11/0.08 s，不能当作原连续 Q3 下界。已在 bound_transfer_audit.json 将这种跨域转用标为 **BOUND_NOT_VALID**，保留原求解记录，仅承认其编码子问题的 bound/gap。没有把实际见证与这种下界拼出“连续 Q3 最优”。

不宣称全局 makespan 最优，不宣称完整列生成收敛，不宣称正式多种子算法优势。

## 6. 验证、计时和保护

5 项模型回归测试通过；9 份占用冲突证书由另一实现复算通过；19 个保存的有限模式整数可行解通过稀疏矩阵、变量边界和目标值复核。4 套完整 Q3 包的原独立核验均为硬约束违规 0、未覆盖样本 0、J_late=0，核验产物 SHA-256 全部一致。全航程核验为 0.5 s 采样并包含阶段/盲区边界与 0.1 s 边界细化，不冒充解析连续无线证明。

每个有限求解记录 incumbent、bound、gap、CPU/wall、节点/冲突或迭代及终止状态。主问题 CP 使用 4 线程，其余采用 1 线程；开发种子 26092511。通信模板仅复用同一结构在 P1.3-B 已经冷建的哈希绑定文件，没有跨结构免费模板，也不把本轮当作冷启动公平比较。中继 stage 的 cpu_s 截止到独立验证前，验证 runtime 单独记录，不声称已有等算力比较。

14053 个既有结果/原始数据/导出文件哈希不变；main 保持 c13306ecbc36933502d1197228e5d80f9f7e40cf。C01 的旧 19+4 低资源方案保留。旧主例、Q4、提交表和论文结论均未替换。

## 7. 交接与停止点

可确认的进展是：现有自主快速运输结构已经能够闭合 Q3；当前研究重点不再是“是否有快速 Q3 见证”。正式主例选择、Q4 重算或提交表替换均属于后续阶段，本轮不执行。

完整运行命令、环境和输出路径见 REPRODUCE.md。原始失败运行、精确有限模型、生成列、成功包和复核证据全部留存。本轮提交独立分支并回传哈希后停止。
'''.replace('TABLE','\n'.join(table))
    (OUT/'GPT_SYNC.md').write_text(body,encoding='utf-8')
    print('REPORT',gate['status'],len(independent['packages']),flush=True)
if __name__=='__main__':main()
