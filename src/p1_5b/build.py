"""Build V0.2 solely from explicitly admitted, hash-bound sources."""
import json,re,hashlib
from pathlib import Path
from src.p1_5b.guard import Guard,ROOT,OUT
PAPER=OUT/'paper'
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def table(headers,rows):
    return '\n'.join(['|'+'|'.join(headers)+'|','|'+'|'.join(['---']*len(headers))+'|']+['|'+'|'.join(map(str,r))+'|' for r in rows])
def main():
    guard=Guard();guard.install()
    def read(p):return guard.json(ROOT/p)
    admission=read('results/p1_5b/admission.json');assert admission['status']=='PASSED'
    comps=read('results/p1_5b/admitted_comparators.json');metrics={r['id']:r['metrics'] for r in comps}
    f=read('results/p1_5a/F13_readmission.json');m=f['metrics'];v=f['independent_validation']
    assert all(metrics['F13'][k]==m[k] for k in metrics['F13'])
    assert m['J_late']==v['hard_violations']==v['uncovered_sample_count']==0
    q1=read('results/p1_5b/q1_sensitivity/summary.json');qv=read('results/p1_5b/q1_sensitivity/validation.json')
    q4=read('results/p1_5a/q4/independent_validation.json');cfg=read('results/p1_5a/q4/config.json')
    blocks=read('results/p1_5a/q4/blocks.json');bound=read('results/p1_5b/fixed_structure_bound.json')
    refs=read('results/p1_5b/references/bibliography.json')
    assert qv['status']==q4['status']=='PASSED'
    assert len(qv['independent_milp_certificates'])==75 and qv['payload_cases']==225
    assert q4['partitions']=={'2':7,'3':6} and len(blocks['blocks'])==4
    q1table=table(['返航余量','最少架次','能耗 / kWh','累计时长 / s','A/B/C架次'],[
        [f"{r['rho']:.0%}",r['sorties'],f"{r['energy_kwh']:.6f}",f"{r['sum_duration_s']:.3f}",'/'.join(str(r['type_counts'].get(k,0)) for k in 'ABC')] for r in q1['levels']])
    trade=table(['方案','归一化交付时效','联合完工 / min','总能耗 / kWh','运输架次','中继架次'],[
        [r['id'],f"{r['metrics']['J_norm']:.6f}",f"{r['metrics']['joint_makespan_s']/60:.4f}",f"{r['metrics']['total_energy_kwh']:.6f}",r['metrics']['transport_sorties'],r['metrics']['relay_sorties']] for r in comps])
    reps=sorted(q4['representatives'],key=lambda r:(r['k'],r['partition_id'] not in cfg['selected']))
    qt=table(['组数','选择原则','资源总缺口 / 件','工作量CV'],[
        [r['k'],'缺口优先' if r['partition_id'] in cfg['selected'] else '均衡优先',r['total_shortage_units'],f"{r['workload_cv']:.6f}"] for r in reps])
    selected={r['k']:r for r in reps if r['partition_id'] in cfg['selected']}
    labels=['A型运输机','B型运输机','C型运输机','A型电池','B型电池','C型电池','中继无人机','中继能源组件']
    kinds=['TUAV_A','TUAV_B','TUAV_C','TBAT_A','TBAT_B','TBAT_C','RUAV','REC']
    qr=table(['资源类型','库存','两组需求','两组缺口','三组需求','三组缺口'],[
        [label,blocks['inventory'][k],selected[2]['resources'][k],selected[2]['shortage'][k],selected[3]['resources'][k],selected[3]['shortage'][k]] for k,label in zip(kinds,labels)])
    bt=table(['块','服务区'],[[i+1,'、'.join(b)] for i,b in enumerate(blocks['blocks'])])
    bibliography=[];evidence=['# 正式文献与正文用途\n','按问题类别组织。以下书目信息来自出版者、标准机构或作者正式记录；所核对范围见每条记录，不将摘要核对表述为全文阅读。具体题目参数和性能结果均不能由这些方法文献代替。\n']
    for i,r in enumerate(refs,1):
        link=('https://doi.org/'+r['doi']) if r.get('doi') else r['official_or_author_source']
        entry=f"[{i}] {', '.join(r['authors'])}. {r['title']}. {r['venue']}, {r['year']}. [{r.get('doi') or '官方出版来源'}]({link})."
        bibliography.append(entry)
        # Exact occurrence locations are checked from the finished body below.
        evidence.append(f"## {i}. {r['category']}\n\n{entry}\n\n- 支撑：{r['supports']}。\n- 不支撑：{r['does_not_support']}。\n- 核对范围：{r['access_scope']}。\n- 原始记录：[{r['title']}]({r['official_or_author_source']})。\n- 正文位置：@@REF_SECTION_{i}@@。\n")
    bibliography.append('[11] 《山区洪涝灾害下无人机运输与通信协同优化》及配套数据与结果提交模板[Z]. 赛题提供资料。')
    evidence.append('## 11. 官方题面与附件\n\n'+bibliography[-1]+'\n\n支撑服务区、货箱、设备库存、时间与物理参数；不支撑本文算法最优性或实际部署。使用位置：第1、3、4节。本地官方文件按继承白名单保存，未推测文件未载明的出版年份或机构。\n')
    def fmt(x,n=3):return f'{x:.{n}f}'
    a=metrics['F12'];z=metrics['F18'];c=metrics['C01'];dt=m['joint_makespan_s']-a['joint_makespan_s'];de=a['total_energy_kwh']-m['total_energy_kwh']
    critical={x['service_id']:x['rho_boundary'] for x in q1['count_breakpoints']}
    vals=dict(F13_MIN=fmt(m['joint_makespan_s']/60),F13_ENERGY=fmt(m['total_energy_kwh']),DT12=fmt(dt,1),DE12=fmt(de),PCT12=fmt(100*de/a['total_energy_kwh'],2),
       DT18=fmt(z['joint_makespan_s']-m['joint_makespan_s'],1),DE18=fmt(m['total_energy_kwh']-z['total_energy_kwh'],3),
       Q1_TABLE=q1table,CRITICAL4=fmt(100*critical['S004'],6),CRITICAL8=fmt(100*critical['S008'],6),
       Q1_ENERGY_INCREASE=fmt(q1['levels'][4]['energy_kwh']-q1['levels'][2]['energy_kwh'],6),Q1_TIME_INCREASE=fmt(q1['levels'][4]['sum_duration_s']-q1['levels'][2]['sum_duration_s']),
       LB_F13=fmt(bound['lower_s']),TT_F13=fmt(bound['upper_transport_s']),TJ_F13=fmt(m['joint_makespan_s']),ET_F13=fmt(m['transport_energy_kwh'],6),SAMPLES=str(v['full_flight_samples']),
       TRADEOFF_TABLE=trade,C01_ENERGY=fmt(c['total_energy_kwh']),C01_MIN=fmt(c['joint_makespan_s']/60),BLOCK_TABLE=bt,Q4_TABLE=qt,Q4_RESOURCE_TABLE=qr,REFERENCES='\n\n'.join(bibliography))
    source=guard.text(PAPER/'PAPER_TEMPLATE.md');used=set(re.findall(r'@@([A-Z0-9_]+)@@',source));assert used==set(vals),(used-set(vals),set(vals)-used)
    for k,value in vals.items():source=source.replace('@@'+k+'@@',value)
    assert '@@' not in source
    sections={};current='摘要'
    for line in source.split('## 参考文献')[0].splitlines():
        if line.startswith(('## ','### ')):current=line.lstrip('# ')
        for number in re.findall(r'\[(\d+)\]',line):sections.setdefault(int(number),set()).add(current)
    assert set(sections)==set(range(1,12)),sections
    ev='\n'.join(evidence)
    for i in range(1,11):ev=ev.replace(f'@@REF_SECTION_{i}@@','；'.join(sorted(sections[i])))
    (PAPER/'PAPER_V02.md').write_text(source)
    (PAPER/'REFERENCE_EVIDENCE_MAP.md').write_text(ev)
    claims=[
      ('统一物理与资源模型','3–4','官方附件、冻结G2几何及参数','质量/体积/电量/充电/库存，不含真实随机信道证明',['results/reset/geometry/transport_uav_types.csv','results/reset/geometry/route_geometry.csv']),
      ('五档225载荷与18/18/18/19/20架次','5','独立标量重算、完整单点子集覆盖MILP','单服务区组合域；不含共享资源并行排程',['results/p1_5b/q1_sensitivity/summary.json','results/p1_5b/q1_sensitivity/validation.json']),
      ('两个架次数阈值与机型更换','5.3','子集能量边界及上下侧重新组批','等号可行；边界上方用1e-8余量探测',['results/p1_5b/q1_sensitivity/all_capacity_feasible_subsets.csv','results/p1_5b/q1_sensitivity/summary.json']),
      ('自主模式成员与比较方案准入','6、8','原独立核验输出完整性、所有选中模式与自主池相符','原核验工件重准入；比较方案本轮未重跑通信物理验证',['results/p1_5b/admission.json','results/p1_5b/admitted_comparators.json']),
      ('F13有限固定结构完工下界','6.3','机型占用工作量/库存下界','只属于F13固定箱组/访问/机型',['results/p1_5b/fixed_structure_bound.json']),
      ('F13零迟到、24+3、能耗与时间','摘要、7、8、11','上阶段重新独立准入的主例及原始执行包','当前阶段性主例，不是全局最优',['results/p1_5a/F13_readmission.json']),
      ('数值全航程通信核验','7.4','69003样本、相位/缺口边界及0.1秒细化','不证明任意连续时刻覆盖或随机鲁棒性',['results/p1_5a/F13_readmission.json']),
      ('近快端局部折中','8','F12/F16/F13/F18及C01各自原核验结果','有限已验证档案；非完整Pareto，非等算力性能结论',['results/p1_5b/admitted_comparators.json','results/p1_5b/figure_data/tradeoffs.csv']),
      ('F13不可拆块、13种分区、分类缺口和CV','9','图可达性、无标签完整枚举、独立峰值扫描与着色','F13固定任务及整中继架次依赖域',['results/p1_5a/q4/blocks.json','results/p1_5a/q4/independent_validation.json']),
      ('主例工作簿与正文统一','附录','同一执行包和工作簿一致性检查','本轮不改工作簿、不进入最终提交排版',['results/p1_5a/submission_consistency.json'])]
    claimtext=['# 科研结论与证据对应\n','主例、比较例和敏感性分开解释；所有来源必须经当前默认拒绝白名单准入。\n']
    for claim,section,method,scope,paths in claims:
        for path in paths:guard.verify(ROOT/path)
        claimtext.append(f'## {claim}\n\n正文：{section}。证据方法：{method}。边界：{scope}。\n\n'+ '\n'.join(f'- `{p}`' for p in paths)+'\n')
    (PAPER/'CLAIM_EVIDENCE_MAP.md').write_text('\n'.join(claimtext))
    dump(PAPER/'build_validation.json',dict(status='PASSED',F13_metrics=m,Q1_grid=q1['levels'],Q4_partitions=q4['partitions'],
        automatic_replacements=vals,citation_sections={k:sorted(v) for k,v in sections.items()},source_accesses=sorted(guard.reads),
        limitations=['No new Q2/Q3 search','No full radio rerun for comparator admission','No final manuscript PDF or submission package'],
        paper_sha256=hashlib.sha256(source.encode()).hexdigest()))
    print('PAPER_BUILT',len(source),len(guard.reads),flush=True)
if __name__=='__main__':main()
