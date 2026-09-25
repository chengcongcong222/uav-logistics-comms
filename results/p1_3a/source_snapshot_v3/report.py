"""Assemble conservative, scope-explicit P1.3-A evidence without re-solving."""
import json, math, platform, subprocess
from pathlib import Path
import scipy, numpy
from src.bench_p1.common import ROOT,write,digest

OUT=ROOT/'results/p1_3a'
PIDS=('A11','AN01','A03')
AXES=('J_norm','joint_makespan_s','total_energy_kwh','relay_sorties')
def read(p):return json.loads(p.read_text())
def rel(p):return str(p.relative_to(ROOT))

def main():
    inputs=read(OUT/'inputs.json');fresh=read(OUT/'warm_readmission.json')
    certificates=read(OUT/'certificate_verification.json')
    certmap={r['certificate']:r for r in certificates['records']}
    resources=read(OUT/'transport_resource_lower_bounds.json')
    models=[];rows=[];raw=[];audits=[];timings={};anomalies=[]
    for pid in PIDS:
        root=OUT/'runs/v2'/pid
        summary=read(root/'model_summary.json');modes=read(root/'group_mode_catalogue.json')
        models.append(dict(pid=pid,**summary,catalogue=rel(root/'group_mode_catalogue.json'),catalogue_sha256=digest(root/'group_mode_catalogue.json'),
            catalogue_origins=sorted(set(m['origin'] for m in modes)),warm_embedding=read(root/'warm_embedding.json')))
        timings[pid]=read(root/'timing.json')
        audits.extend(read(root/'independent_audit.json'))
        for r in read(root/'extreme_results.json'):
            raw.append(r)
            if r['anchor'] not in AXES:continue
            axis=r['anchor'];dest=root/'anchors'/axis
            cert=certmap.get(rel(dest/'lp_lower_bound_certificate.json'))
            if not cert:raise AssertionError(('Missing independently replayed bound',pid,axis))
            # Final audit uses independently replayable rational LP bounds.
            # Raw branch-and-bound values remain visible, never silently
            # promoted after a contradictory or rejected solver result.
            bound=cert.get('integer_objective_lower_bound',cert['lower_bound'])
            ub=r['best_feasible_value'];gap=None if ub is None else max(0.,(ub-bound)/max(abs(ub),1e-12))
            cardinality=bool(axis=='relay_sorties' and ub is not None and bound==ub)
            row=dict(pid=pid,anchor=axis,incumbent=r['incumbent'],best_feasible_value=ub,
                accepted_lower_bound=bound,accepted_bound_basis='EXACT_RATIONAL_LP_PLUS_INTEGER_CEILING' if axis=='relay_sorties' else 'EXACT_RATIONAL_LP',
                verified_incumbent_relative_gap=gap,certificate=cert['certificate'],matrix=r['matrix'],
                raw_solver_dual_bound=r['solver_lower_bound'],raw_solver_mip_gap=r['solver_mip_gap'],
                raw_solver_incumbent_value=r['solver_incumbent_value'],termination_status=r['termination_status'],termination_message=r['termination_message'],
                mip_cpu_s=r['mip_cpu_s'],lp_cpu_s=r['lp_cpu_s'],mip_nodes=r['mip_nodes'],lp_iterations=r['lp_iterations'],mip_iterations=r['mip_iterations'],
                integer_cardinality_optimal_in_declared_catalogue=cardinality,
                optimality_statement='CATALOGUE_CARDINALITY_LB_EQUALS_VALIDATED_WITNESS_UB' if cardinality else 'NOT_PROVEN',
                primal_validation='ORIGINAL_Q3_NUMERICAL_INDEPENDENT_VALIDATOR; not an exact-rational primal certificate',
                bound_status='VALID_FOR_DECLARED_FINITE_MILP',Q3_global_optimal=False,
                candidate_error=r['candidate_error'],zero_late_witness_found=ub is not None,
                infeasibility_claim='NONE: raw status 2 is not independently certified' if r['termination_status']==2 else 'NONE')
            rows.append(row)
            if r['termination_status']==2 or r['candidate_error']:
                anomalies.append(dict(pid=pid,anchor=axis,revision='v2',status=r['termination_status'],candidate_error=r['candidate_error'],
                    conflicts_with_warm=r.get('solver_infeasibility_conflicts_with_verified_warm',False)))
    domain=dict(mode='STRUCTURE_FIXED_EXACT_AUDIT',domain_type='FINITE_DISCRETE_CANDIDATES_WITH_BOUNDED_CONTINUOUS_TIMES',
        base_commit=inputs['base_commit'],physics='G2: UTM49N straight segments and native DEM supercover; unchanged original wireless LOS',Gamma_C_db=0,
        transport_structures=list(PIDS),new_transport_structure_in_p1_2=False,external_solution_structures_used=False,
        fixed=['Transport boxes per sortie, service visit order, UAV type, relative flight and delivery times, fixed transport flight energy',
            'Atomic communication tasks from original 0.5 s sampling / 0.05 s boundary refinement / 2 s guards',
            'Frozen 118 relay site coordinates and eligible task-site relations',
            'Finite catalogue of (task group, endpoint order) modes: observed internal witnesses, all singletons, one-step disjoint observed-group unions in reference order',
            'No splitting atomic tasks or handoffs inside an atom; no new sites',
            'Transport return and relay service endpoints <= 40000 s; relay return bounded by horizon plus site flight tail'],
        released=['Every transport start within preparation and hard-deadline bounds',
            'Same-type transport UAV and battery assignment and pairwise resource orders',
            'Exact-cover selection and recombination of relay group/order modes',
            'All energy-eligible common sites among the frozen 118 for every selected mode',
            'Two relay UAV and six energy-component assignments and pairwise orders'],
        not_fixed_to_warm=['Transport machine orders','Transport battery orders','Relay UAV orders','Relay energy-component orders','Warm relay partition','Warm relay sites'],
        omissions=['Not all possible task subsets or all endpoint permutations are enumerated',
            'No transport box/visit/type reconstruction; no full transport pattern pool',
            'Numerical communication validation, not analytic continuous-trajectory proof'],
        resource_model='Original immediate full recharging with exact two-piece charge graph; no additional charger-port restriction',
        late_hard_layer=1e-4,objectives=list(AXES),transport_sorties='Fixed constant conditional on feasibility',
        arbitrary_weighted_sum=False,tie_break='Only selection among known feasible incumbents: anchor, J_norm, makespan, energy, transport, relay, ID; repeated axis removed. No secondary optimality claim.',
        warm_start='External verified incumbent; v2 has no objective cutoff and supplies no primal MIP start to scipy.milp',
        model_coefficients='Stored binary64 coefficients interpreted exactly as rationals for lower-bound certificates',
        models=models,Q3_global_optimal=False,whole_transport_pool_bound=False)
    write(OUT/'domain.json',domain)
    write(OUT/'extreme_results.json',dict(authority='v2 plus readmitted internal feasible incumbents',results=rows,
        transport_constants=[r for r in raw if r['anchor']=='transport_sorties']))
    write(OUT/'solver_bounds.json',dict(accepted_policy='Replayable exact-rational LP certificates; integer ceiling for relay count. Raw BnB bounds are reported separately, not used for final claims.',
        accepted=rows,raw_v2=raw,raw_v1_files=[rel(OUT/'runs/v1'/p/'extreme_results.json') for p in PIDS],
        exact_rational_certificates=certificates,universal_transport_workload_bounds=resources,anomalies=anomalies))
    write(OUT/'independent_audit.json',dict(hash_bound_p1_2_inputs=len(inputs['sources']),input_admission=rel(OUT/'inputs.json'),
        fresh_revalidated_representatives=fresh,fresh_revalidated_count=len(fresh),
        new_solver_candidates=audits,new_independently_validated_count=sum(r['status']=='INDEPENDENTLY_VALIDATED' for r in audits),
        rejected_candidates_retained=True,validation='Unchanged original independent Q3 validator, full-flight 0.5 s samples and boundary checks; not analytic continuous proof'))
    before=read(OUT/'protected_before.json');changed=[p for p,h in before.items() if not (ROOT/p).is_file() or digest(ROOT/p)!=h]
    branch=subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip()
    main_commit=subprocess.check_output(['git','rev-parse','main'],cwd=ROOT,text=True).strip()
    snapshots=[]
    for p in (OUT/'source_snapshot_v2').glob('*.py'):
        current=ROOT/'src/bench_p1_3a'/p.name
        snapshots.append(dict(path=rel(current),matches_executed_snapshot=digest(p)==digest(current)))
    protection=dict(protected_files=len(before),changed=changed,all_unchanged=not changed,branch=branch,main_commit=main_commit,
        main_unchanged=main_commit=='c13306ecbc36933502d1197228e5d80f9f7e40cf',executed_source_checks=snapshots)
    write(OUT/'protection_check.json',protection)
    required=('joint_makespan_s','total_energy_kwh','relay_sorties')
    gates={axis:any(r['anchor']==axis and r['best_feasible_value'] is not None and r['verified_incumbent_relative_gap'] is not None for r in rows) for axis in required}
    ready=all(gates.values()) and not changed and protection['main_unchanged'] and all(r['matches_executed_snapshot'] for r in snapshots)
    gate=dict(status='P1_3A_FINITE_DOMAIN_AUDIT_READY' if ready else 'P1_3A_BOUND_BLOCKED',requirements=gates,
        scope='A11 and AN01 have validated incumbents and exact-rational relaxation bounds in declared partial finite domains; A03 zero-late witness remains absent',
        no_full_structure_optimality_claim=True,no_global_pareto_claim=True,no_global_Q3_optimality_claim=True,
        no_formal_algorithm_comparison=True,formal_seeds_used=False,external_structures_used=False,
        raw_solver_anomalies_not_accepted_as_proofs=True,main_Q4_submission_untouched=not changed,
        blocked_reasons=[] if ready else ['See requirements and protection_check.json'],stop_after_this_phase=True)
    write(OUT/'gate.json',gate)
    write(OUT/'environment.json',dict(python=platform.python_version(),scipy=scipy.__version__,numpy=numpy.__version__,solver='SciPy bundled HiGHS',
        platform=platform.platform(),seed=26092511,threads_per_solver=1,mip_time_limit_per_anchor_s=90,lp_time_limit_s=60,
        note='Two revisions retained. Time limits are wall-clock solver limits, process CPU measured separately. This is not an equal-CPU benchmark.',timings=timings))
    md=['# P1.3-A：有限结构精确极值审计','',f"Gate：`{gate['status']}`。基于 `{inputs['base_commit']}`，开发分支 `{branch}`。",
        '', '本轮建立了可导出矩阵、可复算下界的 MILP；释放运输与中继资源分配和次序。结果仅覆盖声明的部分候选域，没有求透整个 Q3，也没有证明整个运输模式池的能力边界。',
        '', '## 最重要的结论','',
        '不依赖中继目录的运输资源下界：A11 ≥ 6300.781644 s（105.013027 min），AN01 ≥ 8069.140624 s，A03 ≥ 8688.858064 s。A11 的 B 型运输占用合计 12601.563287 s、原资源只有 2 架，因此完工时间不能低于其一半。此结论固定箱组、访问顺序和机型，允许任意中继分组及资源次序；不能扩展为整个运输模式池的下界。',
        '', '## 单目标审计结果','', '| 结构 | 目标 | 已验证可行上界 | 接受的下界 | 相对 gap |', '|---|---|---:|---:|---:|']
    for r in rows:
        ub='无零迟到见证' if r['best_feasible_value'] is None else f"{r['best_feasible_value']:.9f}"
        gap='—' if r['verified_incumbent_relative_gap'] is None else f"{100*r['verified_incumbent_relative_gap']:.4f}%"
        md.append(f"| {r['pid']} | {r['anchor']} | {ub} | {r['accepted_lower_bound']:.9f} | {gap} |")
    md += ['', '各行是分别优化的结果，不应拼成一个不存在的综合方案。下界采用精确有理数重算的 LP 拉格朗日证书；中继架次再向上取整。原始求解器 dual bound、MIP gap、节点、终止状态与 CPU 均另存，不能与这里按独立验证上界重算的 gap 混淆。',
        '', 'A11、AN01 在当前中继分组/端点次序目录内的最少中继架次为 4：整数下界为 4，且存在已独立验证的 4 架次见证。它不证明其他中继分组或端点排列下也至少需要 4 架次。A03 没有零迟到暖启动见证；求解器的不可行状态没有独立不可行证书，因此不宣称整个 A03 物理域或 Q3 不可行。',
        '', '## 实际方案比较','', '| 来源 | J_late | J_norm | 完工 s | 总能耗 kWh | 运输/中继架次 |', '|---|---:|---:|---:|---:|---:|']
    comparisons=[]
    for ident in ('A11_Q3_001','D26092511_005'):
        r=next(r for r in inputs['sources'] if r['id']==ident);comparisons.append((ident,r['metrics']))
    for r in rows:
        if r['incumbent'] and (r['incumbent']['id'],r['incumbent']['metrics']) not in comparisons:
            comparisons.append((r['incumbent']['id'],r['incumbent']['metrics']))
    for ident,m in comparisons:
        md.append(f"| {ident} | {m['J_late']:.9g} | {m['J_norm']:.9f} | {m['joint_makespan_s']:.6f} | {m['total_energy_kwh']:.9f} | {m['transport_sorties']}/{m['relay_sorties']} |")
    new=[r for r in audits if r['status']=='INDEPENDENTLY_VALIDATED']
    improvements=[]
    for r in rows:
        prior=[s['metrics'][r['anchor']] for s in inputs['sources'] if s['pid']==r['pid'] and s['zero_late_eligible']]
        if prior and r['best_feasible_value'] is not None and r['best_feasible_value']<min(prior)-1e-7:
            improvements.append(f"{r['pid']} / {r['anchor']}：{min(prior):.9f} → {r['best_feasible_value']:.9f}（{r['incumbent']['id']}）")
    md += ['', '本轮相对全部已准入 P1.2 候选的单目标改进：'+('；'.join(improvements) if improvements else '没有刷新已知单目标最好值；新增可行包不能等同于性能提升。')]
    md += ['',f"本轮新求解器候选中有 {len(new)} 套通过原独立 Q3 验证。另有 54 个 P1.2 内部输入经提交内清单与验证文件哈希绑定，其中 6 个代表包重新执行完整核验（5 个满足零迟到硬层，1 个 A03 仅作为软迟到历史对照）。没有把 54 个哈希核对说成 54 次新物理验证。",
        '', '## 数学域与实现限制','',
        '每种结构的箱组、访问顺序、机型和相对飞行过程固定；运输起飞时刻、同型无人机/电池的分配与次序自由。中继目录包含已验证输入中出现的任务组及端点次序、全部原子单任务组，以及不相交历史任务组的一步并集。求解器可重新组合目录内分组，并选择 118 个冻结站点中的共同可行站点。没有固定暖启动资源次序。',
        '', '仍未枚举所有任务子集或所有端点排列；没有原子区间内部交接；运输返回与中继服务端点受 40000 s 显式时域约束。单架次能耗使用区间并集的精确分段仿射式，充电使用原函数的分段等式图，不以保守跨度能耗或充电下界替代。完整限制、矩阵与候选目录见 domain.json 和 runs/v2。',
        '', '所有目标分别求解，没有任意加权和。确定性 tie-break 仅用于从已有可行上界中选代表，不宣称次级目标最优。SciPy 当前驱动没有提交 primal MIP start；已验证暖启动作为外部可行上界保留。正式种子和评价权重未参与本轮。',
        '', '## 异常处理与可信边界','',
        'v1 完整保留：发现非时间目标下完工辅助变量允许松弛，不能将其与真实完工的差值当成模型错误；还发生 AN01 能耗目标的求解器不可行状态与暖启动见证冲突。v2 删除目标截断，修正完工辅助变量检查。迟到仅因数值误差越过硬层时，允许固定整数选择后的 LP 原始可行解修复；其更严迟到约束只用于构造可行解，从不用于下界。',
        '', '最终接受的下界不依赖存在异常的分支定界状态，而由导出的二进制浮点系数精确解释为有理数，重算带有限变量盒残差修正的拉格朗日界。物理上界仍采用原数值独立验证及模型嵌入容差，不是有理数原始解证明。未通过验证的候选保留错误记录，绝不计入可行上界。',
        '', f"7 项数学回归测试通过；{len(certificates['records'])} 个下界证书通过逐矩阵有理数重算。新输出均在 results/p1_3a；{len(before)} 个既有文件哈希核对未变={not changed}。main 仍为 `{main_commit}`。",
        '', '## UNVERIFIED_EXTERNAL_CHALLENGE','',
        '用户提供的外部汇总点（例如 98.51 min / 70.358 kWh / 24+3，以及约 118.10 min / 68.869 kWh / 24+4）没有在本轮独立验证，也未读取其箱组、路线或结构。它们只作为背景挑战，不进入目标、截断或停止规则。现有三个固定运输结构的通用时间下界均高于第一个外部时间数字；若其口径一致且真实可行，需要改变运输结构才能达到，但本轮不判断外部真实性或整个运输模式池是否包含这类结构。',
        '', '## 停止点与后续决策','',
        '本轮到 P1.3-A 停止。READY 仅表示已经形成清楚候选域内的有效上界、可复算下界和 gap，不表示连续时间与能耗方向已经求透。尚未开展全运输模式池审计、分解/列生成、正式算法比较或新 Pareto 前沿；旧主例、Q4、提交表与论文结论没有替换。']
    (OUT/'GPT_SYNC.md').write_text('\n'.join(md)+'\n',encoding='utf-8')
    print(gate['status'],len(new),'new validated packages;',len(before),'protected files')

if __name__=='__main__':main()
