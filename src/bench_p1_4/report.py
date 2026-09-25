"""Audit executed P1.4 results and form a finite validated epsilon archive."""
import json,math,subprocess
from pathlib import Path
import numpy as np
from scipy.sparse import csr_matrix
from src.bench_p1_4.common import *

AXES=('J_norm','joint_makespan_s','total_energy_kwh','transport_sorties','relay_sorties')
TOL=(1e-9,1e-6,1e-8,0,0)
def dominates(a,b):
    return all(a[k]<=b[k]+t for k,t in zip(AXES,TOL)) and any(a[k]<b[k]-t for k,t in zip(AXES,TOL))

def main():
    records=read(OUT/'candidate_index.json');q2=[];q3=[];archive=[];finite=[];primals=[];screens=[]
    prior={read(p)['signature']:p.stem for p in (ROOT/'results/p1_3b/representatives').glob('*.json')}
    for r in records:
        p=ROOT/r['package'];v=read(p/'validation.json');assert digest(p/'validation.json')==r['validation_sha256']
        assert v['J_late']<=1e-8 and v['hard_deadline_violations']==0
        for f,h in v['artifact_sha256'].items():
            target=ROOT/f if f.startswith('results/') or Path(f).is_absolute() else p/f
            assert digest(target)==h,f
        q2.append(dict(id=r['id'],metrics=r['metrics'],package=r['package'],hashes=len(v['artifact_sha256']),
            validation_sha256=r['validation_sha256'],historical_structure_match=prior.get(r['signature']),new_structure=r['signature'] not in prior))
    for p in sorted((OUT/'screening').glob('*/q3/*/solutions/*/validation_0.5.json')):
        v=read(p);assert v['hard_violations']==0 and v['uncovered_sample_count']==0 and v['J_late']<=1e-8
        for f,h in v['artifact_sha256'].items():assert digest(ROOT/f)==h,f
        w=read(p.parent/'witness.json');m=w['metrics'];assert m['relay_sorties']<=3 and m['joint_makespan_s']<=6500+1e-7
        pid=v['pareto_id'];src=OUT/'q2/pareto_schedules'/pid;copybase=OUT/'screening'/pid/'q2/pareto_schedules'/pid
        for f in ['missions.json','q2_sorties.csv','q2_box_delivery.csv']:assert digest(src/f)==digest(copybase/f)
        row=dict(id=p.parent.name,pid=pid,source='P1_4_NEW',metrics=m,package=str(p.parent.relative_to(ROOT)),validation_sha256=digest(p),
            source_structure_signature=next(r['signature'] for r in records if r['id']==pid),validation=v)
        q3.append(row);archive.append(row)
    for p in sorted((ROOT/'results/p1_3c').glob('*/q3/*/solutions/*/validation_0.5.json')):
        v=read(p);assert v['hard_violations']==0 and v['uncovered_sample_count']==0 and v['J_late']==0
        for f,h in v['artifact_sha256'].items():assert digest(ROOT/f)==h
        m=read(p.parent/'witness.json')['metrics']
        if m['joint_makespan_s']<=6500:archive.append(dict(id=p.parent.name,pid=v['pareto_id'],source='READMITTED_P1_3C_ANCHOR',metrics=m,package=str(p.parent.relative_to(ROOT)),validation_sha256=digest(p)))
    for p in sorted((OUT/'screening').glob('*/C2_SITE*/result.json')):
        if '_RELAY_' in p.parent.name:continue
        r=read(p);screens.append(dict(pid=r['pid'],result=str(p.relative_to(ROOT)),witnesses=len(r['witnesses']),
            termination=[x['master']['status'] for x in r['iterations']],zero_witness_is_not_continuous_physical_infeasibility=True))
    paths=list((OUT/'transport_runs').glob('*/result.json'))+list((OUT/'screening').glob('*/C2*/**/result.json'))
    for p in sorted(paths):
        r=read(p)
        if 'incumbent' not in r:continue
        entry=dict(path=str(p.relative_to(ROOT)),raw=r,scope='Conservative transport grid' if 'transport_runs' in p.parts else 'Declared fixed-time column or conservative coupled-grid subproblem',
            global_continuous_Q3_bound=False)
        if 'master_' in p.parent.name:
            rows=[x for x in q3 if x['pid']==p.parts[p.parts.index('screening')+1]]
            if rows and r.get('dual_bound') is not None and r['dual_bound']>rows[0]['metrics']['joint_makespan_s']+1e-7:
                entry.update(continuous_bound_transfer_status='BOUND_NOT_VALID',reason='Encoded conservative objective exceeds actual continuous witness; original encoded bound retained only in its declared scope.')
        finite.append(entry)
    for p in (OUT/'screening').glob('*/C2*/**/model.npz'):
        ip=p.parent/'incumbent.npy'
        if not ip.exists():continue
        d=np.load(p);x=np.load(ip);a=csr_matrix((d['data'],d['indices'],d['indptr']),shape=tuple(d['shape']));v=a@x
        err=max(0,float(np.max(d['lower']-v)),float(np.max(v-d['upper'])),float(np.max(-x)),float(np.max(x-1)),float(np.max(abs(x-np.rint(x)))))
        assert err<1e-5
        r=read(p.parent/'result.json');assert abs(d['objective']@x-r['incumbent'])<1e-5
        assert r['dual_bound'] is None or r['dual_bound']<=r['incumbent']+1e-5
        primals.append(dict(model=str(p.relative_to(ROOT)),maximum_violation=err,phase=r['phase']))
    front=[r for r in archive if not any(dominates(o['metrics'],r['metrics']) for o in archive if o['id']!=r['id'])]
    budgets=[]
    for b in [6155,6250,6350,6500]:
        eligible=[r for r in archive if r['metrics']['joint_makespan_s']<=b+1e-7]
        winner=min(eligible,key=lambda r:(r['metrics']['transport_sorties'],r['metrics']['total_energy_kwh'],r['metrics']['J_norm'],r['metrics']['joint_makespan_s']))
        energy=min(eligible,key=lambda r:r['metrics']['total_energy_kwh'])
        budgets.append(dict(cap_s=b,eligible=len(eligible),lexicographic_best_known_id=winner['id'],metrics=winner['metrics'],minimum_observed_energy_id=energy['id'],
            minimum_transport_sorties_proven=False,minimum_total_energy_proven=False,scope='Within this finite independently validated archive, not all pool structures'))
    assert all(budgets[i+1]['metrics']['transport_sorties']<=budgets[i]['metrics']['transport_sorties'] for i in range(3))
    audit=dict(status='PASSED',Q2_packages=len(q2),new_Q3_packages=len(q3),readmitted_Q3_anchors=len(archive)-len(q3),matrix_primals=len(primals),
        Q2=q2,Q3=q3,matrix_checks=primals,physical_validation='Original independent whole-flight numerical checker, 0.5s with phase/gap boundaries and 0.1s boundary refinement; no analytic continuous radio proof')
    write(OUT/'independent_audit.json',audit);write(OUT/'solver_bounds.json',finite);write(OUT/'q3_screening.json',screens)
    write(OUT/'validated_archive.json',archive);write(OUT/'epsilon_budget_results.json',budgets)
    write(OUT/'near_fast_frontier.json',dict(status='WITHIN_THIS_FINITE_VALIDATED_ARCHIVE_ONLY',axes=AXES,tolerances=TOL,solutions=front,
        global_pareto_proven=False,restricted_nondominance_proven=False,enumeration_complete=False))
    protected=read(OUT/'protected_files.json');changed=[f for f,h in protected.items() if not (ROOT/f).exists() or digest(ROOT/f)!=h];assert not changed,changed[:5]
    main=subprocess.check_output(['git','rev-parse','main'],text=True,cwd=ROOT).strip();assert main=='c13306ecbc36933502d1197228e5d80f9f7e40cf'
    write(OUT/'protection_check.json',dict(status='PASSED',files=len(protected),changed=changed,main=main))
    paper=read(ROOT/'results/paper_v01/BUILD_CHECK.json');assert paper['paper_status']=='V01_DRAFT_NOT_FINAL_SUBMISSION'
    pm=read(ROOT/'results/paper_v01/artifact_manifest.json')
    for f,h in pm['files'].items():assert digest(ROOT/f)==h,f
    write(OUT/'gate.json',dict(status='P1_4_NEAR_FAST_TRADEOFFS_VERIFIED_PAPER_V01_READY',new_Q3_packages=len(q3),independently_validated_Q2=len(q2),
        finite_archive_nondominated_points=len(front),paper_base='842d950eba19374a287351b9b839fb446ff55d14',paper_status=paper['paper_status'],
        main_Q4_submission_replaced=False,formal_comparison=False,global_optimality_proven=False,complete_pareto_front=False,
        G2_Q1_reserve_sensitivity_complete=False,new_main_Q4_complete=False))
    base=next(r for r in archive if r['id']=='T02_C2_SITE_RELAY_00_Q3')['metrics']
    lines=['| 时间预算 s | 档案内按运输架次→总能耗选出的方案 | 联合完工 min | 总能耗 kWh | 运输＋中继 | J_norm |','|---:|---|---:|---:|---:|---:|']
    for b in budgets:
        m=b['metrics'];lines.append(f"| {b['cap_s']} | {b['lexicographic_best_known_id'].split('_')[0]} | {m['joint_makespan_s']/60:.4f} | {m['total_energy_kwh']:.6f} | {m['transport_sorties']} + {m['relay_sorties']} | {m['J_norm']:.9f} |")
    resultlines=[]
    for r in sorted(q3,key=lambda r:(r['metrics']['joint_makespan_s'],r['metrics']['total_energy_kwh'])):
        m=r['metrics'];resultlines.append(f"- {r['pid']}：J_late={m['J_late']:.9g}，{m['joint_makespan_s']:.6f} s，{m['joint_makespan_s']/60:.4f} min，{m['total_energy_kwh']:.6f} kWh，{m['transport_sorties']}+{m['relay_sorties']}，J_norm={m['J_norm']:.9f}。")
    candidate=budgets[1];m=candidate['metrics'];trade=dict(id=candidate['lexicographic_best_known_id'],time_increment_s=m['joint_makespan_s']-base['joint_makespan_s'],
        energy_saving_kwh=base['total_energy_kwh']-m['total_energy_kwh'],energy_saving_percent=100*(base['total_energy_kwh']-m['total_energy_kwh'])/base['total_energy_kwh'],
        transport_sorties_reduction=base['transport_sorties']-m['transport_sorties'])
    write(OUT/'recommended_tradeoff.json',dict(**trade,status='RECOMMENDATION_ONLY_NOT_OFFICIAL_MAIN',criterion='Smallest declared non-anchor epsilon budget (6250s), then minimum observed transport sorties and energy'))
    text=f'''# P1.4 快端 ε 约束折中搜索与论文 V0.1

Gate：P1_4_NEAR_FAST_TRADEOFFS_VERIFIED_PAPER_V01_READY。
基于 842d950eba19374a287351b9b839fb446ff55d14，分支 p1-4-fast-frontier-paper。用户要求的算法与论文两条线均已形成实际文件；论文是完整工作稿，非最终提交稿。

## 1. 本轮实际成果

共 {len(q2)} 套运输候选通过原独立验证，定向冷建并筛查 {len(set(r['pid'] for r in screens))} 个运输结构（{len(screens)} 次分解运行），得到 {len(q3)} 套新的零迟到 Q3 执行包。新包均满足 Gamma=0、118 个冻结站点、2 架中继、6 个能源组件、最多 3 个中继架次和 6500 s 总时间预算。

{chr(10).join(resultlines)}

## 2. 四档预算下的已知最好折中

{chr(10).join(lines)}

表内是统一合并档案中的最好已知结果，不是各预算下已证明的全局最少架次或最低能耗。保留 J_norm、联合时间、总能耗、运输架次、中继架次五维比较，绝不合并两类架次替代支配判断。档案共 {len(archive)} 个已验证点（包括 {len(archive)-len(q3)} 个 P1.3-C 锚点），其中 {len(front)} 个在这个有限集合内非支配；不称完整 Pareto 前沿。

6250 s 档阶段候选 {trade['id'].split('_')[0]} 相对旧 T02：时间增加 {trade['time_increment_s']:.3f} s，节省 {trade['energy_saving_kwh']:.6f} kWh（{trade['energy_saving_percent']:.3f}%），少 {trade['transport_sorties_reduction']} 个运输架次。这是基于自己的已验证快端锚点构造的效率—资源折中，不以外部截图为求解目标或验证标尺。正式主例尚未替换。

## 3. 求解方法与本轮真实边界

原 2903 模式池不变。四档运输主问题先以架次为单一目标，再把当前找到的最佳架次数固定、以运输能耗为目标。每次 75 s wall limit、4 个 CP 工作线程，种子 26092511；CPU 与 wall 分开记录。搜索过程中曾在较紧的 6250 s 档找到比先前 6350 s 档更少的 24 架次，于是把该结构送回 6350 s 档做了一次同架次能耗细化。全部 9 个运输优化运行保留原状态和 gap，没有删除失败或较弱结果。

运输能耗生成仅是候选筛选手段，不把它冒充 Q3 总能耗优化。Q3 对所选结构重新冷建本结构通信区间与全部冻结站点关系，沿用站点—中继机一致性主问题、动态中继列、精确区间并集能量和充电。Q3 主问题在 6500 s 可行域内优先压缩联合时间；中继列先追求完整覆盖，再检查架次，最后在当前固定时刻和生成目录内最小化中继能耗。最终按实际联合完工落入各 ε 档。它不是对整个 Q3 做了精确的字典序最优求解。

三架次上限同时进入受限列主问题，所有选出的架次分别占用 2 架中继和 6 个能源组件；不是仅在结果展示时裁剪。中继能耗目标为微 kWh 整数缩放，原始系数目标的 bound/gap 只属于该固定时刻、有限目录与缩放域。

F18 初次主问题给出四种“中继机—站点”组合，两轮有限列子问题仍有未覆盖任务。最后只对它做一次必要约束反馈：最多三架次必然最多使用三种这样的组合。该约束不是充分条件，也没有把失败变成物理不可行 cut；加入后，新模式通过原精确能耗、资源日历和独立执行验证，得到约104.929分钟、70.084kWh、24+3。初始源码及失败模型保存在 diagnostics/initial_sources 和原运行目录。

另外枚举每个已筛查结构的全部冻结站点覆盖掩码，均证明至少需要三个不同站点才能完整覆盖原子任务；新成功方案的三个中继架次匹配该必要下界。作用域仍是各自固定运输结构和不拆原子任务的冻结候选关系，不是全题所有结构的计数最优证明。

部分候选在保守网格主问题中无解或未获得见证，见 q3_screening.json。该结论不扩大为原连续物理问题不可行，更不能说“所有23架次都不可行”。未筛查的运输候选保持 Q2 身份。保守网格 makespan bound 若高于连续执行见证，禁止跨域转用，标为 BOUND_NOT_VALID；没有全局 Q3 时间下界或全池计数最优性结论。本轮不是正式等 CPU、多种子比较。

## 4. 论文 V0.1

results/paper_v01/PAPER_V01.md 已形成完整摘要、问题与假设、符号、统一物理模型、Q1/Q2/Q3/Q4方法和结果、局限、结论及数据附录；约 1.61 万字符，5 张数据表、2 幅可复建标准图。数据冻结于 P1.3-C，T01/T02并列快端，T03固定时刻代表通信兼容性，C01代表低资源端，A11作为历史基准。6个原Q3执行包的84项产物哈希核对通过，119项来源文件留有哈希。未把写作核对冒充重新运行物理验证。

本轮 P1.4 新结果在本目录的 PAPER_RESULTS_ADDENDUM.md 独立列出，避免一边声称冻结V1、一边悄悄替换正文数字。正式采用新主例后应统一升级正文、Q4和提交表。

关键待办：G2口径下的Q1安全余量敏感性数值尚需补算，旧不同口径数据未混入；Q4仅保留A11历史案例，不能冒充新快端方案Q4；正式参考文献、版式与最终主例的路线/资源图仍待定稿。旧稿的“180秒五种子性能优势”没有带入新稿。

## 5. 验证与保护

3 项新增约束/目标测试通过；{len(q2)} 个 Q2 包、{len(q3)} 个新 Q3 包已由原独立程序验证，执行产物哈希复核通过；{len(primals)} 个中继有限模型整数解完成独立矩阵约束及目标值复核。全航程通信为 0.5 s 采样加阶段/间隙边界和 0.1 s 边界细化，非解析连续无线证明。

{len(protected)} 个既有结果、原始数据、导出和旧论文文件哈希不变；main、旧正式主例、Q4及提交工作簿均未改动。所有代码、模型、日志、执行包、论文与复现命令随独立分支提交。本轮结束后不自动重算Q4或替换正式工作簿。
'''
    (OUT/'GPT_SYNC.md').write_text(text,encoding='utf-8')
    (OUT/'PAPER_RESULTS_ADDENDUM.md').write_text('# 论文 V0.1 的 P1.4 结果补充（尚未并入冻结正文）\n\n'+chr(10).join(lines)+'\n\n上述结果均零迟到，完整Q3独立验证通过；在有限验证档案中按运输架次、总能耗选取，非全局最优证明。\n\n'+chr(10).join(resultlines)+'\n\n正式主例、对应Q4与提交表尚待一致更新。\n',encoding='utf-8')
    print('REPORT',len(q2),'Q2',len(q3),'new Q3',len(front),'finite archive nondominated',flush=True)
if __name__=='__main__':main()
