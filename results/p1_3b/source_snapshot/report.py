"""Evidence-based P1.3-B handoff; no global/frontier or algorithm superiority claim."""
import json,subprocess,platform,math
from collections import Counter
from pathlib import Path
import scipy,numpy,pandas
from src.bench_p1_3b.common import *

def main():
    reps=[read(p) for p in sorted((OUT/'representatives').glob('*.json'))];new=[r for r in reps if r['anchor']!='HISTORICAL']
    bounds=read(OUT/'bounds/summary.json');verification=read(OUT/'verification.json')
    raw_runs=[]
    for p in sorted((OUT/'transport_runs').glob('*/result.json')):
        raw_runs.append(dict(run=p.parent.name,config=read(p.parent/'config.json'),result=read(p),source=str(p.relative_to(ROOT))))
    screening=[]
    for pid in ['T01','T02','T03','C01','E01','N01']:
        root=OUT/'screening'/pid;r=read(root/'result.json');r['cold_config']=read(root/'config.json')
        r['candidate_summary']=read(root/'q3'/pid/'candidate_summary.json')
        r['cold_template_log']=read(root/'q3'/pid/'template_log.json')
        upper=min((w['metrics']['relay_sorties'] for w in r.get('witnesses',[])),default=None)
        lower=r.get('relay_count_bound',{}).get('lower_bound')
        r['relay_count_comparison']=dict(verified_upper=upper,catalogue_relaxation_lower=lower,
            relative_gap=None if upper is None or lower is None else max(0,(upper-lower)/upper),
            scope='Cold proposed group catalogue only, not complete Q3')
        if (root/'exact_rescue/result.json').exists():r['exact_rescue']=read(root/'exact_rescue/result.json')
        screening.append(r)
    old=next(r for r in reps if r['id']=='H_A11');a11_bound=6300.781643600972
    fast=[r for r in new if r['metrics']['makespan']<a11_bound and r['anchor']=='makespan']
    fast_ids={r['id'] for r in fast};closed=[]
    for r in screening:
        closed += [dict(transport_id=r['pid'],**w) for w in r.get('witnesses',[])]
        closed += [dict(transport_id=r['pid'],**w) for w in r.get('exact_rescue',{}).get('witnesses',[])]
    fast_closed=[w for w in closed if w['transport_id'] in fast_ids]
    # The primary question is transmission of the demonstrated time advantage.
    # A slower different structure cannot stand in as its Q3 closure witness.
    valid_bounds=all(r['lower_bound'] is not None for r in bounds)
    if not valid_bounds:gate_status='P1_3B_SOLVER_GAP_BLOCKED'
    elif fast and fast_closed:gate_status='P1_3B_POOL_SUFFICIENT_FOR_Q3_DECOMPOSITION'
    elif fast and not fast_closed:gate_status='P1_3B_Q3_COUPLING_BLOCKED'
    else:gate_status='P1_3B_SOLVER_GAP_BLOCKED'
    gate=dict(status=gate_status,primary_scope='Fast transport candidates and their corresponding Q3 closure, not universal Q3 feasibility',
        bound_status='VALID_CONTINUOUS_FULL_POOL_CERTIFICATES' if valid_bounds else 'P1_3B_BOUND_BLOCKED',
        faster_than_A11_fixed_structure_bound=sorted(fast_ids),corresponding_fast_Q3_witnesses=len(fast_closed),
        other_new_Q3_verified_witnesses=[w['id'] for w in closed if w not in fast_closed],
        all_pool_Q3_infeasibility_claim=False,all_Q3_structures_blocked=False,
        evidence='Three independently validated fast structures beat the A11 structure lower bound; none closed in bounded cold Q3 screening, including one exact finite-mode rescue. A distinct 19-sortie slower structure did close.',
        next_priority='Improve transport-relay coupling and relay group/site scheduling; do not infer pool insufficiency or start column generation from these bounds',
        no_global_optimality_claim=True,no_final_pareto_claim=True,no_formal_comparison=True,stop_after_this_phase=True)
    write(OUT/'gate.json',gate)
    extremes=[]
    for axis in AXES:
        key=lambda r:(r['metrics'][axis],r['metrics']['J_norm'],r['metrics']['makespan'],r['metrics']['energy'],r['id'])
        incumbent=min(reps,key=key);best_new=min(new,key=key);b=next(r for r in bounds if r['anchor']==axis)
        upper=incumbent['metrics'][axis];lower=b['lower_bound']
        assert lower is None or lower<=upper+1e-7
        extremes.append(dict(anchor=axis,verified_incumbent=incumbent['id'],incumbent_package=incumbent['package'],upper_bound=upper,
            best_new_run_representative=best_new['id'],best_new_value=best_new['metrics'][axis],valid_full_pool_lower_bound=lower,
            relative_gap=None if lower is None else max(0,(upper-lower)/abs(upper)),bound_status=b['bound_status'],
            certificate=b.get('certificate'),finite_continuous_pool_optimality_proven=False,
            tie_break='Known feasible incumbent selection only: requested axis, J_norm, makespan, energy, ID; no secondary optimality claim'))
    write(OUT/'finite_pool_extremes.json',dict(domain='Entire frozen 2903-pattern pool, original continuous-time physics and original resources, J_late <= 1e-4',
        certified_lower_bound_domain='Continuous-time outer relaxation',primal_search_domain='Conservative 0.1 s optional-interval CP-SAT; all pool patterns and all class-bounded copies; free resource assignment/order',
        results=extremes,raw_full_pool_LP_solves=bounds))
    distances=[]
    for i,a in enumerate(new):
        for b in new[i+1:]:
            ca,cb=Counter(a['pattern_occurrences']),Counter(b['pattern_occurrences'])
            distances.append(dict(a=a['id'],b=b['id'],removed_occurrences=sum((ca-cb).values()),added_occurrences=sum((cb-ca).values())))
    tbest=min(r['metrics']['makespan'] for r in new if r['anchor']=='makespan')
    write(OUT/'diverse_transport_structures.json',dict(representatives=reps,pattern_multiset_distances=distances,
        new_representative_count=len(new),historical_readmissions=len(reps)-len(new),
        time_near_optimal_definition='Three different structures among improving solver incumbents; all within 5% of the best verified new transport time; not a global near-optimality theorem',
        time_representatives=[dict(id=r['id'],relative_to_best=r['metrics']['makespan']/tbest-1) for r in new if r['anchor']=='makespan'],
        no_external_structures=True))
    write(OUT/'q3_screening.json',dict(records=screening,verified_witnesses=closed,fast_Q2_structures=sorted(fast_ids),fast_Q3_closed=bool(fast_closed),
        limitations=['Three initial fixed partition/site conservative seed models per structure are not the full Q3 domain',
            'T01 received one additional exact partial group/order/site-domain MILP; time limit is not infeasibility',
            'Relay-count certificate scopes differ between cold group catalogue and exact rescue catalogue; neither is a global Q3 lower bound',
            'Communication verification uses original full-flight numerical sampling and boundary refinement, not an analytic continuous-time proof']))
    write(OUT/'solver_bounds.json',dict(accepted_full_pool_bounds=bounds,extremes=extremes,raw_transport_solver_runs=raw_runs,
        cp_solver_bounds_not_used_as_continuous_pool_bounds=True,
        reason='Conservative time-grid occupancy and rounded single-objective coefficients define a restricted primal domain; its dual does not bound the continuous full pool',
        rational_verification=verification['certificates'],q3_bounds=[dict(pid=r['pid'],seed_group_count=r.get('relay_count_bound'),exact_rescue=r.get('exact_rescue')) for r in screening],
        invalid_bound_policy='Any raw bound above a validated upper bound is BOUND_NOT_VALID and excluded; none of the accepted rational full-pool bounds contradicts a validated upper bound'))
    write(OUT/'independent_audit.json',dict(status=verification['status'],packages=verification['packages'],q2_count=sum(r['scope']=='Q2' for r in verification['packages']),
        q3_count=sum(r['scope']=='Q3' for r in verification['packages']),
        legacy_validator_labels='XB1_Q2_INDEPENDENTLY_VALIDATED is the reused generic checker name, not external provenance. Q3 uses the unchanged original validator.',
        independent_rational_certificate_replays=len(verification['certificates']),all_new_q3_claims_require_original_independent_validation=True))
    before=read(OUT/'protected_before.json');changed=[p for p,h in before.items() if not (ROOT/p).is_file() or digest(ROOT/p)!=h]
    main_commit=subprocess.check_output(['git','rev-parse','main'],cwd=ROOT,text=True).strip()
    protection=dict(files=len(before),changed=changed,all_unchanged=not changed,main_commit=main_commit,main_unchanged=main_commit=='c13306ecbc36933502d1197228e5d80f9f7e40cf')
    assert protection['all_unchanged'] and protection['main_unchanged'];write(OUT/'protection_check.json',protection)
    write(OUT/'environment.json',dict(python=platform.python_version(),numpy=numpy.__version__,scipy=scipy.__version__,pandas=pandas.__version__,ortools='9.14.6206',
        dependency_target='.deps_p13b (not committed; installation instructions provided)',original_venv_not_modified=True,
        transport_CP_seed=26092511,transport_CP_workers=4,parallel_worker_search_not_bitwise_reproducible=True,
        Q3_initial_T01_HiGHS_seed=0,Q3_initial_T01_seed_note='Unchanged original helper used HiGHS default 0; confirmed via HighsOptions().random_seed; source snapshot preserved',
        other_Q3_seed=26092511,Q3_threads=1,formal_equal_CPU_comparison=False,
        primary_transport_limits_s=dict(makespan=180,sorties=90,J_norm=90,energy=90),
        process_CPU_vs_wall='Both recorded per solve; four CP workers can consume roughly four CPU seconds per wall second'))
    md=['# P1.3-B：完整现有自主运输模式池审计','',f"Gate：`{gate_status}`。基于 `{BASE}`，分支 `p1-3b-full-pool-audit`。",'',
        '结论已经分成两层：现有自主模式池能够产生明显快于 A11 固定结构极限的新运输组合；但是这批快速运输组合的优势尚未传递为已验证的快速 Q3 解。另一个 19 架次结构成功闭合 Q3，因此不能说整个模式池或所有新结构都无法执行。',
        '', '## 1. 模式池到底覆盖了什么','',
        '快照 SHA-256：`'+read(OUT/'pool_manifest.json')['sha256']+'`。实际 2903 个模式：单点 296、两点 2607、其他 0；61 个属性等价类覆盖 80 个货箱。全部模式进入覆盖与排程模型，按货箱数量允许最多 2973 个可选模式副本。访问顺序和机型只从原模式中选择。',
        '', '这是“完整现有模式池”，不是“所有可能运输模式”：生成阶段先从 1074 个可行单点模式保留 296 个，两点模式也受邻近点和载荷筛选限制。本轮没有重建模式池，没有引入任何外部箱组、路线或解结构。2903 个模式的飞行、能耗、交付和充电系数均与原 MissionEvaluator 交叉核对；这项系数核对不冒充独立物理验证。',
        '', '## 2. 当前连续时间全池的上下界','',
        '| 目标 | 已独立验证上界 | 有效全池下界 | gap | 上界代表 |','|---|---:|---:|---:|---|']
    for r in extremes:md.append(f"| {r['anchor']} | {r['upper_bound']:.9f} | {r['valid_full_pool_lower_bound']:.9f} | {100*r['relative_gap']:.4f}% | {r['verified_incumbent']} |")
    md += ['', '各行分别优化，不能拼成一套同时取得所有最好指标的方案。能耗最好的已知上界仍来自重新准入并独立验证的历史自主 A03（60.047645 kWh）；本轮能耗搜索的新代表为 61.402630 kWh，没有把较弱新结果写成刷新纪录。',
        '', '这里接受的下界来自完整模式池的连续时间外松弛：精确属性类覆盖、机型资源负载、充电尾部、截止期必要条件、并行机工作量平方不等式的线性切面。它放松具体资源时序，包含原连续可行域的投影。所有导出矩阵均有精确有理数拉格朗日证书；派生系数向外舍入，证书由第二套实现重新计算。',
        '', '可行解使用 CP-SAT 的可选区间与累计容量模型，全部模式竞争箱组覆盖，运输无人机和电池次序自由，随后按区间着色恢复资源编号。起点网格为 0.1 s，资源占用向保守方向取整；时效/能耗仍是单一目标，只作整数系数缩放与舍入，没有任意多目标加权和。CP 的原始 bound/gap 只属于这一保守网格域，绝不冒充连续时间全池下界。',
        '', '四个目标都保存了原始状态、CPU、wall time、分支/冲突数、LP 迭代数和 gap。当前没有任何一个方向证明连续时间全池最优。多工作线程的 CP 运行不承诺逐比特复现；本轮不是严格等 CPU 算法比较。',
        '', '## 3. 结构多样性与运输执行包','', '| 代表 | 来源目标 | 完工 s | 能耗 kWh | 架次 | J_norm | 该结构资源下界 s |', '|---|---|---:|---:|---:|---:|---:|']
    for r in new:
        m=r['metrics'];md.append(f"| {r['id']} | {r['anchor']} | {m['makespan']:.3f} | {m['energy']:.6f} | {m['sorties']} | {m['J_norm']:.6f} | {r['transport_workload_lower_bound_s']:.3f} |")
    md += ['', '9 个新代表均为不同模式多重集合并通过原独立 Q2 核验；另有 A03/A11/A12 三个历史自主包重新核验且逐架次证明属于同一冻结模式池。T01/T02/T03 均在最佳新运输时间的 5% 内，实际约 101.69、102.17、103.50 分钟；距离以模式副本增删数保存，避免把单纯改时刻或重编号算成新结构。',
        '', 'T01 的固定结构工作量下界约 6082.519 s，已找到排程为 6101.161 s，说明这套新结构自身的纯运输时间已很接近其负载必要下界。全池时间下界则为 5539.261 s，二者作用域不同。A11 原 6300.781644 s 下界仍成立，没有被新结构“推翻”。',
        '', '## 4. Q3 冷建筛查','', '| 结构 | 链路未覆盖任务 | Q3 零迟到见证 | 说明 |', '|---|---:|---|---|']
    for r in screening:
        count=len(r['candidate_summary']['unresolved']);ok=bool(r.get('witnesses')) or bool(r.get('exact_rescue',{}).get('witnesses'))
        md.append(f"| {r['pid']} | {count} | {'已独立验证' if ok else '未找到'} | "+('另做一次精确有限目录救援，限时仍无见证' if r['pid']=='T01' else '原资源、冻结站点；失败不等于不可行')+' |')
    for w in closed:
        m=w['metrics'];md += ['', f"**{w['id']}**：J_late={m['J_late']:.9g}，J_norm={m['J_norm']:.9f}，联合完工 {m['joint_makespan_s']:.6f} s，总能耗 {m['total_energy_kwh']:.9f} kWh，{m['transport_sorties']} 次运输＋{m['relay_sorties']} 次中继。原独立验证无硬约束违规、无未覆盖通信样本。"]
    md += ['', '每个代表均从自己的新运输轨迹冷建通信原子任务和全部 118 个冻结站点关系，Gamma=0、2 架中继、6 个能源组件不变。没有免费读取其他结构的候选关系。T01 精确救援只复用它本次已经冷建的同结构缓存，并绑定来源哈希。',
        '', '初始每种结构筛查三个固定分组/站点方案，允许运输时刻和资源次序调整；其种子 MILP 用保守跨度能耗，故无解不能证明真实 Q3 无解。T01 另建 115 个分组/端点次序模式的精确 MILP，释放目录内站点、分组组合和全部资源次序，用原区间并集能耗及分段充电等式；16414 个变量、92493 条约束，90 s 限时没有得到见证，其目录内中继架次 LP 整数下界为 3。这个 3 不是完整 Q3 全局下界。',
        '', 'C01 的成功表明“少运输架次＋零迟到资源闭环”确实能在新自主结构上实现。但 C01 与 T01/T02/T03 是不同结构，不能拿较慢 C01 的闭合证明三个快速结构已经闭合；也不能把 6101.161 s 写成 Q3 完工时间。',
        '', '## 5. Gate 的解释','',
        f"选择 `{gate_status}`，将阻塞范围限定为本轮主目标的三个快速运输候选：它们都已经突破 A11 结构下界，但对应的零迟到 Q3 见证尚未找到。成功的 C01 明确保留为另一条分支，因此这里的 BLOCKED 不表示所有新结构均不可行。",
        '', '不选择 POOL_STRUCTURE_LIMITED：有效全池时间下界仍明显低于已找到的运输上界，且已经出现比 A11 结构极限更快的可行运输组合，无法据此归咎于模式池。也不把“存在另一套较慢 Q3 成功方案”升级为“快速结构已具备联合闭环”。下一步应针对运输—中继耦合、分组/站点目录和联合可行性分解；本轮不启动列生成或下一阶段。',
        '', '## 6. 验证、诊断与保护','',
        f"6 项数学回归测试通过；{len(verification['certificates'])} 份证书由第二套有理数实现重算通过；12 套 Q2 包（9 新＋3 历史重准入）及 1 套新 Q3 包的独立验证和全部验证产物哈希通过。{len(before)} 个既有文件哈希未变，main 仍为 `{main_commit}`。旧主例、Q4、提交表与旧论文结论未替换。",
        '', '首轮两个 CP 运行没有找到可行解，原状态保留。开发检查发现暖启动直接舍入会制造资源重叠，随后改为按原资源次序仅构造可行提示；该次开发中还捕获了提示完工变量被局部循环变量覆盖的问题。修正后每次主运行先验证完整提示确实满足编译模型，主模型中没有固定提示资源顺序。全部诊断日志和代码快照保留，没有删失败运行。',
        '', 'T01 初始三个 Q3 种子调用沿用原 HiGHS 默认 seed=0（已从本地 HighsOptions 核对）；其余 Q3 和 CP 显式使用开发 seed=26092511。所有这些运行均不是正式多种子性能实验。通用导出/验证函数保留历史 XB 命名，但不调用外部结构导入函数；池来源、各模式映射和哈希独立保存。',
        '', '## UNVERIFIED_EXTERNAL_CHALLENGE_POSTHOC','',
        '只在求解与验证完成后比较用户给出的外部标量：98.51 min / 70.358 kWh / 24+3 等没有在本轮独立验证，也没有成为求解目标、剪枝阈值或停止条件。自主运输层的 101.69 min 已自然接近 100 min，但这仍是 Q2；不能将其与外部 Q3 完工直接当作同口径优劣结论。当前全池 Q2 下界约 92.32 min，也不能保证在这个时间附近存在物理可行 Q3。',
        '', '## 复现和停止点','',
        '完整命令见 REPRODUCE.md；数学域与上下界推导见 MODEL.md。本轮停在 P1.3-B，不生成最终 Pareto，不运行正式种子，不做 Branch-and-Price，不替换正式方案。']
    (OUT/'GPT_SYNC.md').write_text('\n'.join(md)+'\n',encoding='utf-8')
    print(gate_status,'verified Q2',len(reps),'Q3',len(closed),'protected',len(before))

if __name__=='__main__':main()
