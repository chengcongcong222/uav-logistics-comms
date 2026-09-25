"""Assemble P1.1 evidence and a conservative admission gate; never run formal seeds."""
import hashlib,importlib.metadata,json,math,platform,subprocess,sys
from pathlib import Path
from src.bench_p1.common import ROOT,OUT,METHODS,DEV_SEEDS,write,digest,canonical
from src.bench_p1.preferences import OBJECTIVES

def calibration(rows,scope):
    vectors=[[r['metrics'][k] for k in OBJECTIVES[scope]] for r in rows]
    if not vectors:return dict(status='UNAVAILABLE_NO_VERIFIED_CANDIDATE',offsets=None,scales=None)
    low=[min(v[i] for v in vectors) for i in range(len(vectors[0]))];high=[max(v[i] for v in vectors) for i in range(len(vectors[0]))]
    fallback=[1,12000,100,80] if scope=='Q2' else [1,16000,120,80,20]
    scales=[b-a if b>a else fallback[i] for i,(a,b) in enumerate(zip(low,high))]
    return dict(status='DEVELOPMENT_DERIVED_NOT_YET_FORMAL_FROZEN',objectives=OBJECTIVES[scope],offsets=low,scales=scales,maxima=high,zero_span_axes=[OBJECTIVES[scope][i] for i,(a,b) in enumerate(zip(low,high)) if a==b],positive_physical_fallback=fallback,source_count=len(rows),source_packages=[r['package'] for r in rows],no_clipping=True,includes_soft_late_calibration_candidates=True,formal_freeze=False)

def main():
    audit=json.loads((OUT/'audit_all.json').read_text());runs=audit['runs'];rows=audit['records']
    for scope,batch in [('Q2','Q2_120_v3'),('Q3','Q3_300_v4')]:
        assert len([r for r in runs if batch in r['root']])==2*len(METHODS[scope]),'Final development batch incomplete'
    for name,count in [('integration_tests.log',34),('cpu_regression_tests.log',5)]:
        text=(OUT/name).read_text();assert f'Ran {count} tests' in text and '\nOK\n' in text,name
    before=json.loads((OUT/'protected_before.json').read_text());changed=[p for p,h in before.items() if not (ROOT/p).exists() or digest(ROOT/p)!=h]
    write(OUT/'hash_preservation.json',dict(protected_files=len(before),changed=changed,pass_all=not changed,base_commit='c13306ecbc36933502d1197228e5d80f9f7e40cf'))
    write(OUT/'independent_audit.json',dict(verified_packages=len(rows),verified_Q2=sum(r['scope']=='Q2' for r in rows),verified_Q3=sum(r['scope']=='Q3' for r in rows),failures=audit['failures'],scope='Only complete in-budget packages; Q3 intermediate Q2 packages are not full Q3 successes',record_file='audit_all.json',negative_hard_deadline_test=json.loads((OUT/'negative_audit/result.json').read_text())))
    # Keep development levels separate. No cross-level method ranking.
    write(OUT/'smoke_summary.json',dict(formal=False,runs=runs,scope='interface and accounting coverage, not superiority statistics'))
    chosen={'Q2':'Q2_120_v3','Q3':'Q3_300_v4'}
    normalized={scope:calibration([r for r in rows if r['scope']==scope and chosen[scope] in r['run']],scope) for scope in chosen}
    write(OUT/'normalization.json',normalized)
    queries={}
    for scope,norm in normalized.items():
        qs=[]
        if norm['offsets'] is not None:
            source=[r for r in rows if r['scope']==scope and chosen[scope] in r['run']]
            for i,k in enumerate(OBJECTIVES[scope]):
                if i==0:continue
                vals=sorted({r['metrics'][k] for r in source}) if 'sorties' in k else sorted({norm['offsets'][i]+f*(norm['maxima'][i]-norm['offsets'][i]) for f in [0,.25,.5,.75,1]})
                for cap in vals:
                    valid=[r for r in source if r['metrics']['J_late']<=1e-4 and r['metrics'][k]<=cap]
                    qs.append(dict(metric=k,cap_native_units=cap,zero_late_witnesses=len(valid),classification='ATTAINED_IN_DEVELOPMENT_ARCHIVE' if valid else 'NO_KNOWN_ZERO_LATE_WITNESS_NOT_INFEASIBILITY'))
        queries[scope]=dict(queries=qs,integer_rule='Distinct attained development sortie counts; no assertion all globally attainable integers enumerated',status='DEVELOPMENT_QUERIES_NOT_FORMAL_FROZEN')
    write(OUT/'budget_queries.json',queries)
    final=[r for r in runs if any(x in r['root'] for x in chosen.values())]
    alns=[r for r in final if r['method']=='ALNS'];q3=[r for r in final if r['scope']=='Q3']
    pairs=[]
    for scope,batch in chosen.items():
        methods=['POOL','POOL_CHALLENGE'] if scope=='Q2' else METHODS['Q3']
        for seed in DEV_SEEDS:
            paths=[OUT/'runs'/batch/f'{m}_{seed}'/'pool_signature.json' for m in methods]
            hashes=[digest(p) if p.exists() else None for p in paths]
            initials=[OUT/'runs'/batch/f'{m}_{seed}'/'q2/pareto_schedules/P0001/missions.json' for m in METHODS[scope]]
            initial_hashes=[digest(p) if p.exists() else None for p in initials]
            pairs.append(dict(scope=scope,seed=seed,methods=methods,sha256=hashes,initial_methods=METHODS[scope],initial_sha256=initial_hashes,same_initialization=all(h is not None for h in initial_hashes) and len(set(initial_hashes))==1,same_pool=all(h is not None for h in hashes) and len(set(hashes))==1))
    write(OUT/'paired_pool_checks.json',pairs)
    admissions=dict(Q2_ALNS=dict(implemented=True,adaptive_sampling_exercised=all(r['adaptive_selections']>3 for r in alns),all_four_objective_axes_exercised=all(len(r['preference_ids'])>=4 for r in alns),small_domain='small_domain_certificate.json',claim='Problem adaptation with bounded development checks, not state of the art'),uniform=dict(current='HISTORICAL_FIVE_DESTROY_THREE_REPAIR_WITH_EXPLICIT_PREFERENCE_INTERFACE',historical='c13306e results unchanged; final v3 restores operators and acceptance, earlier shared-operator runs are diagnostic',formal_method_identity_resolution_required=False),Q3=dict(flows=METHODS['Q3'],full_witnesses_by_run={r['root']:r['verified_complete_scope_packages'] for r in q3},all_five_search_preference_axes_exercised=False,reason='Current bounded flow visits first three preference axes and one transport structure; transport/relay sortie axes not yet exercised in whole-flow original-instance search',sequential_positive_control_completed=(OUT/'fixtures/sequential_positive/validation.json').exists()),formal_admitted=False)
    examples=[]
    for seed in DEV_SEEDS:
        rs=[r for r in rows if 'Q2_120_v3' in r['run'] and r['method']=='ALNS' and r['seed']==seed]
        base=next(r for r in rs if r['pid']=='P0001')
        best=min(rs,key=lambda r:(r['metrics']['J_late'],r['metrics']['J_norm']))
        examples.append(dict(seed=seed,base=base['package'],best=best['package'],base_J_late=base['metrics']['J_late'],best_J_late=best['metrics']['J_late'],basic_improvement=best['metrics']['J_late']<base['metrics']['J_late']))
    admissions['Q2_ALNS']['independently_checked_improvement_examples']=examples
    write(OUT/'baseline_admission.json',admissions)
    blockers=[
      dict(id='Q3_ARCHIVE_DRIVER_INCOMPLETE',reason='Q3驱动目前只执行三个固定分组请求与一个运输种子，尚未成为预算内多偏好档案生成器；运输架次和中继架次偏好尚未驱动整体候选生成/选择。三条流程原型与向量工具测试不能替代该项集成。'),
      dict(id='FORMAL_CALIBRATION_FREEZE',reason='已生成具体开发归一化与预算数值，但应在Q3多偏好驱动准入后才能正式冻结；600秒Q3正式预算尚未确认。本轮不以有限请求提前结束的用时宣称完整档案预算已校准。')]
    if not (OUT/'fixtures/sequential_positive/validation.json').exists():blockers.append(dict(id='Q3_SEQUENTIAL_POSITIVE_CONTROL',reason='Positive physical baseline test has not passed'))
    if changed:blockers.append(dict(id='HISTORY_CHANGED',reason=changed))
    if audit['failures']:blockers.append(dict(id='PHYSICAL_AUDIT_FAILED',reason=audit['failures']))
    accounting=[r for r in final if r['observed_cpu_s']>r['cpu_cap_s']+.2 or r.get('maximum_observed_threads')!=1 or r.get('observed_children') or r['evaluation_preferences_opened'] or not r['input_trace_available'] or r['exit_code'] not in [0,-9]]
    if accounting:blockers.append(dict(id='ACCOUNTING_OR_ISOLATION',reason=accounting))
    if not all(p['same_pool'] and p['same_initialization'] for p in pairs):blockers.append(dict(id='PAIRED_POOL_MISMATCH',reason=[p for p in pairs if not p['same_pool'] or not p['same_initialization']]))
    versions={n:importlib.metadata.version(n) for n in ['numpy','scipy','pandas','rasterio','pyproj']}
    resolved=dict(status='PREFLIGHT_RESOLVED_WITH_EXPLICIT_BLOCKERS_NOT_FORMAL_FROZEN',base_commit='c13306ecbc36933502d1197228e5d80f9f7e40cf',formal_run_permitted=False,branch='p1-preflight',geometry='G2_UTM49N_STRAIGHT_NATIVE_SUPERCOVER_V1',Gamma_C_db=0,development_seeds=DEV_SEEDS,development_budgets_Q2=[30,120],development_budgets_Q3=[30,120,300],proposed_formal_cpu_s=dict(Q2=180,Q3=600),Q3_formal_cpu_confirmed=False,method_scope=admissions,budget_unit='whole archive generation, not per preference',bootstrap_scales=dict(Q2=[1,12000,100,80],Q3=[1,16000,120,80,20]),numerical_development_normalization='normalization.json',numerical_development_budget_queries='budget_queries.json',source_hashes={str(p.relative_to(ROOT)):digest(p) for p in (ROOT/'src/bench_p1').glob('*.py')},original_data_sha256=json.loads((OUT/'source_hashes.json').read_text()),search_preference_sha256={s:digest(OUT/'inputs'/f'search_{s}.json') for s in ['Q2','Q3']},evaluation_preferences_used=False,environment=dict(python=sys.version,platform=platform.platform(),libraries=versions),site_pool=json.loads((OUT/'site_provenance.json').read_text()),blockers=blockers)
    write(OUT/'resolved_protocol.json',resolved)
    lines=['# P1.1 前线交接','', '**状态：P1_BLOCKED；本轮停止，不启动正式比较。**','',
      '已完成原题/附件核对、统一指标与偏好日志、实际ALNS适配、三条Q3流程、隔离缓存/计时、开发冒烟及完整执行包独立审计。旧主例、Q4、工作簿与旧论文均未替换。','',
      f'开发共 {len(runs)} 次运行；独立验证 {len(rows)} 个完整检查点，其中 Q2 {sum(r["scope"]=="Q2" for r in rows)} 个，Q3 {sum(r["scope"]=="Q3" for r in rows)} 个。Q3流程产生的中间运输包计入Q2检查点，不冒充Q3成功。','',
      '启动包20项测试原样通过，新增14项接口/真实两箱有限域检查通过；另有CPU截止回归和保持资源不重叠的真实硬截止负例。不同证据层不能互相替代。','',
      '|层|方法|开发预算/s|种子|完整本层包|找到零迟到|结束阶段|','|---|---|---:|---:|---:|---|---|']
    lines += ['|'+ '|'.join(map(str,[r['scope'],r['method'],r['cpu_cap_s'],r['seed'],r['verified_complete_scope_packages'],r['zero_late_found'],r['phase']['phase']]))+'|' for r in final]
    lines += ['', '全部阶段仅重复使用两个开发种子，执行包数含重复初始化与诊断结果，不是独立实验样本数量。以上为接口开发记录，不是正式胜负表。未找到零迟到不会通过放宽约束转为成功，也不等于模型不可行。', '', '## 本轮发现', '',
      '- 旧6位小数去重确实可能抹去生产容差下的支配差别；P1改为保留精确不同向量，历史结果未重写。',
      '- 旧资源引擎暗中加载历史P01-P03轨迹与任务。P1已替换初始化，仅共享118个冻结坐标，任务模板与边关系全部私有冷建并计CPU。',
      '- 30/120秒Q3主要耗在冷建任务—站点关系；300秒才进入资源闭环。这是计算成本证据，不是联合算法性能优势证据。',
      '- Q3_120_v2运行中有一次运输候选偏好接线修改，整批仅作诊断、不作校准。最终300秒批次冻结搜索源码重跑；独立审计适配器修复另行记录，不改变搜索轨迹。',
      '- 顺序基线阳性测试识别人为1e-5秒分离缓冲排除合法相接区间；P1核已修复，阳性包全航程独立验证通过，并同预算重跑全部Q3方法。该fixture不是冷启动算法成绩。',
      '- 最终开发Q3候选尚无零迟到见证；普通物资软迟到与硬截止违反严格区分。只要独立核验通过，可作可执行开发见证，但不替换A11。',
      '- 原始题目Office公式单独提取，未用历史讨论替代题面。', '', '## 为什么不能签READY', '']
    lines += [f'- {b["id"]}: {b["reason"]}' for b in blockers]
    lines += ['', '## 下一轮最小工作范围', '',
      'Q3还需从三个固定分组请求升级为预算内多偏好档案驱动，并让运输架次和中继架次偏好进入整体候选生成/选择；然后冻结共同归一化、预算断面和Q3正式CPU上限。历史uniform身份和顺序修补可行正例已在本轮修正并检查。没有授权在本轮追加正式多种子实验。', '',
      '复现：见 REPRODUCE.md。完整状态见 gate.json；逐运行与独立验证见 smoke_summary.json、independent_audit.json、audit_all.json。分支保留全部开发失败与诊断批次，main仍为c13306e。']
    (OUT/'GPT_SYNC.md').write_text('\n'.join(lines)+'\n')
    gate=dict(gate='P1_BLOCKED',formal_run_permitted=False,performance_superiority_proven=False,global_pareto_proven=False,development_runs=len(runs),verified_Q2_packages=sum(r['scope']=='Q2' for r in rows),verified_Q3_packages=sum(r['scope']=='Q3' for r in rows),history_preserved=not changed,blockers=blockers,stop_after_this_preflight=True)
    files=[p for p in OUT.rglob('*') if p.is_file() and p.name not in ['gate.json','gate_build.log'] and 'partial' not in p.parts and '__pycache__' not in p.parts and not p.name.endswith('.tmp')]+list((ROOT/'src/bench_p1').glob('*.py'))+list((ROOT/'validation/p1_setup').glob('*.py'))
    gate['artifact_sha256']={str(p.relative_to(ROOT)):digest(p) for p in files};write(OUT/'gate.json',gate)
    print(json.dumps({k:v for k,v in gate.items() if k!='artifact_sha256'},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
