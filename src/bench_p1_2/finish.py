"""Evidence-derived P1.2 gate, deliberately no formal comparison permission."""
import csv, json, subprocess
from pathlib import Path
from src.bench_p1.common import ROOT, write, digest, signature
from src.bench_p1_2.driver import OUT, AXES, SEEDS

def main():
    original=json.loads((OUT/'protected_before.json').read_text())
    changed=[p for p,h in original.items() if not (ROOT/p).is_file() or digest(ROOT/p)!=h]
    write(OUT/'history_preservation.json',dict(checked=len(original),changed=changed))
    admission=json.loads((OUT/'warm_seed_readmission.json').read_text())
    summaries=[];blockers=[];new_packages=[];runs=[];bridge=[];fresh_templates=True
    for seed in SEEDS:
        root=OUT/'runs'/str(seed)
        if not (root/'outcomes.json').exists():
            blockers.append(f'{seed}: no complete outcomes');continue
        events=[json.loads(line) for line in (root/'anchor_trace.jsonl').read_text().splitlines()]
        outcomes=json.loads((root/'outcomes.json').read_text())
        timing=json.loads((root/'timing.json').read_text()) if (root/'timing.json').exists() else {}
        runs.append(dict(seed=seed,timing=timing,outcomes=outcomes))
        for pid in ['A11','AN01','A03']:
            base=root/'q2/pareto_schedules'/pid
            template_log=json.loads((root/'q3'/pid/'template_log.json').read_text())
            if any(t['cache_hit'] for t in template_log):
                fresh_templates=False;blockers.append(f'{seed}/{pid}: unexpected inherited template hit')
            site_summary=json.loads((root/'q3'/pid/'candidate_summary.json').read_text())
            if site_summary['sites']!=118:blockers.append(f'{seed}/{pid}: frozen site count changed')
            missions=json.loads((base/'missions.json').read_text())
            shapes={m['mission_id']:{k:m[k] for k in ['uav_type','box_ids','service_sequence','boxes_by_service']} for m in missions}
            for shape in shapes.values():
                shape['box_ids']=sorted(shape['box_ids'])
                shape['boxes_by_service']={k:sorted(v) for k,v in shape['boxes_by_service'].items()}
            flights={r['sortie_id']:r for r in csv.DictReader((base/'q2_sorties.csv').open())}
            tasks=list(csv.DictReader((root/'q3'/pid/'guarded_atomic_tasks.csv').open()))
            physical_tasks=[dict(structure=shapes[t['transport_sortie_id']],
                     relative_start_s=round(float(t['service_start_s'])-float(flights[t['transport_sortie_id']]['preparation_start_s']),8),
                     relative_end_s=round(float(t['service_end_s'])-float(flights[t['transport_sortie_id']]['preparation_start_s']),8)) for t in tasks]
            bridge.append(dict(seed=seed,pid=pid,transport_structure_signature_without_ids=signature(sorted(shapes.values(),key=signature)),
                     communication_signature_without_ids=signature(sorted(physical_tasks,key=signature)),tasks=len(tasks),
                     guarded_duration_sum_s=sum(float(t['service_duration_s']) for t in tasks)))
        for axis in AXES:
            ee=[e for e in events if e['anchor']==axis]
            feedback=[e for e in ee if e['action']=='independently_verified_feedback']
            required=('transport_retention_and_q3_target_selection','transport_portfolio_expansion',
                      'transport_structure_entered','q3_lp','joint_adjustment',
                      'relay_proposal_selection','relay_neighbor_attempt',
                      'q3_feedback_archive_update','challenge_target_selection','final_anchor_retention')
            missing=[x for x in required if not any(e['action']==x for e in ee)]
            row=dict(seed=seed,anchor=axis,new_validated_packages=len(feedback),
                     structure_feedback=sorted({e['pid'] for e in feedback}),
                     task_hashes=sorted({e['tasks_hash'] for e in feedback}),
                     missing_trace_stages=missing,
                     feedback=[{k:e[k] for k in ['id','pid','origin','metrics','tasks','structure_hash','tasks_hash','package']} for e in feedback])
            if missing or not feedback:blockers.append(f'{seed}/{axis}: incomplete actual search trace')
            if axis=='relay_sorties':
                relevant=[b for b in bridge if b['seed']==seed and b['pid'] in row['structure_feedback']]
                row['cross_structure_feedback']=(len({b['transport_structure_signature_without_ids'] for b in relevant})>=2
                    and len({b['communication_signature_without_ids'] for b in relevant})>=2)
                row['distinct_relay_counts']=sorted({e['metrics']['relay_sorties'] for e in feedback})
                if not row['cross_structure_feedback']:blockers.append(f'{seed}: no cross-structure relay feedback')
            summaries.append(row);new_packages.extend(feedback)
        for o in outcomes:
            if o['metrics']['J_late']>1e-4:blockers.append(f'{seed}: zero-late layer replaced')
        opens=[json.loads(x) for x in (root/'input_opens.jsonl').read_text().splitlines()]
        forbidden=[r for r in opens if not r['auditing'] and any(s in r['path'] for s in
                   ['/results/xb1/','/results/reset/q3/B','/results/reset/q2/pareto_schedules/B','evaluation_only_'])]
        if forbidden:blockers.append(f'{seed}: forbidden search inputs')
    failures=list((OUT/'runs').glob('*/q3/*/solutions/*/validation_failure.json'))
    if failures:blockers.append('Independent validator rejected exported candidates: inspect retained failure files')
    for e in new_packages:
        result=json.loads((ROOT/e['package']/'validation_0.5.json').read_text())
        assert result['status']=='P1_Q3_INDEPENDENTLY_VALIDATED'
        for p,h in result['artifact_sha256'].items():
            if digest(ROOT/p)!=h:blockers.append('Audited artifact modified: '+p)
    if changed:blockers.append('Protected history changed')
    if admission['status']!='READMITTED':blockers.append('A11 not readmitted')
    main_head=subprocess.check_output(['git','rev-parse','main'],cwd=ROOT,text=True).strip()
    if main_head!='c13306ecbc36933502d1197228e5d80f9f7e40cf':blockers.append('main moved')
    status='P1_2_BLOCKED' if blockers else 'P1_2_ANCHOR_DRIVER_READY'
    write(OUT/'anchor_trace_summary.json',dict(mode='DIAGNOSTIC_WARM',runs=runs,anchors=summaries,
         structure_to_communication_bridge=bridge))
    gate=dict(gate=status,blockers=blockers,mode='DIAGNOSTIC_WARM',base_commit='b7c8352332cee5c41ba75a9c6e2eb19254206e42',
              main=main_head,formal_run_permitted=False,P1_3_started=False,formal_cold_start_eligible=False,
              performance_superiority_proven=False,global_pareto_proven=False,
              admission_scope='WARM_FINITE_STRUCTURE_PORTFOLIO_AND_LOCAL_RELAY_SEARCH',cold_start_driver_admitted=False,
              warm_packages_readmitted=len(json.loads((OUT/'warm_portfolio_readmission.json').read_text())),
              new_verified_Q3_packages=len(new_packages),development_seeds=SEEDS,
              history_preserved=not changed,protected_files=len(original),
              frozen_common_sites=118,Gamma_C_db=0,normalization_formally_frozen=False,
              run_private_templates_built_fresh=fresh_templates,
              independent_validation_step_s=.5,unit_tests=9,artifact_manifest_file='artifact_manifest.json')
    write(OUT/'gate.json',gate)
    lines=['# P1.2 前线交接','',f'**Gate：{status}。本轮停止，不进入 P1.3 或正式比较。**','',
           '## 接口准入结果','',
           '新增独立 DIAGNOSTIC_WARM 入口。五个 anchor 分别进入运输结构保留、Q3候选选择、连续联合调整、中继合并/拆分/换站提案排序、实际结果反馈和下一轮挑战目标选择。运输架次与中继架次仍为独立坐标。',
           '',f'A11 首先通过原 P1 独立检查；随后共重验 {gate["warm_packages_readmitted"]} 个自主暖启动包。两个开发种子新导出并完整独立验证 {len(new_packages)} 个 Q3 包，包含重复指标或同一暖启动的局部调整，不是独立算法样本或新非支配点计数。',
           '', '中继 anchor 保留不同运输结构，分别冷建通信任务/站点关系，实际联合闭环后按中继架次反馈选择，再将所选结构送入下一次挑战。日志明确区分保护零迟到的当前解与可以软迟到的结构探索候选。',
           '', '去除任务ID、架次ID和箱号列举顺序后，A11与AN01的运输结构签名、相对通信区间签名均不同。二者各25个区间，保障时长之和分别为12028.90625秒和11882.03125秒；A03为19个区间、11326.375秒。中继anchor中A11与AN01的新闭环结果最终都为4次中继，再由真实指标反馈选择挑战对象；这证明跨结构路径接通，不证明两种结构的中继数必然不同。',
           '', '## 已知内部 warm seed','',
           '只使用自主 A11、AN01、A03，具体包及重验哈希见 warm_portfolio_readmission.json。A11_Q3_001 仍为旧主例；其本轮0.5秒全航程核验含67,890采样点，通信漏保与硬截止违规均为0。这是旧见证的重新准入，不是本轮新性能。',
           '', '## 开发数值观察','',
           '|种子|anchor|最终保留|J_late|J_norm|联合完工/s|总能耗/kWh|运输/中继架次|',
           '|---|---|---|---:|---:|---:|---:|---|']
    for run in runs:
        for o in run['outcomes']:
            m=o['metrics'];lines.append(f'|{run["seed"]}|{o["anchor"]}|{o["best_id"]}|{m["J_late"]:.6g}|{m["J_norm"]:.9f}|{m["joint_makespan_s"]:.3f}|{m["total_energy_kwh"]:.6f}|{m["transport_sorties"]}/{m["relay_sorties"]}|')
    lines += ['', '以上仅用于检查目标接线。主例、Q4、工作簿和旧论文均未替换。每个方向最多两种运输结构、每结构一次连续调整和一个中继邻域尝试，再做一次反馈目标挑战；未增加搜索以追求好看数字。',
              '', '## 实现范围及未完成项','',
              '- 运输结构来自已重验自主有限暖启动库；本轮证明结构保留/调度的目标接入，不证明冷启动模式生成、ALNS或任意新箱组均已接入这套驱动。',
              '- 连续挑战固定暖启动的同型资源次序和通信端点事件次序，保留原方案指标上界；外层中继邻域允许合并、拆分、换站，使用当前目标的公开启发式排序后才实际求解。有限邻域失败不等于不可行。',
              '- 架次在固定结构LP内是常数，优化由外层不同运输结构/中继分组选择实现；未把常数系数冒充连续优化作用。运输方向保留19架次结构作为探针，但本轮没有用软迟到探针替代25架次零迟到层。',
              '- 档案保留全部已验证诊断包，没有进行非支配裁剪；同一anchor标量并列时按ID稳定选代表元。因此运输anchor可以显示旧A11，虽然其他候选改善了它的非主目标。这不是主例推荐，也不是非支配性证据；正式比较前仍需独立处理零权重并列和档案质量。',
              '- 同一开发种子中的五个方向共享该次运行新建的私有模板；不同种子不复用缓存。只共享118个冻结坐标，不导入历史任务/边关系。',
              '- 计时单列运行初始化、建图、搜索/导出与独立审计；历史暖启动与站点发现成本未追回，模块导入在run计时外，不作等算力比较。',
              '- 独立检查保留原0.5秒全航程采样与边界细化规则，不声称解析连续时间证明。',
              '- 尚未正式冻结归一化、预算断面与CPU上限；没有正式种子或64组评价权重，没有算法优势或完整Pareto前沿结论。',
              '', '## 未验证的外部挑战数字','',
              '用户转述的98.51分钟等外部标量只作为后续讨论背景，本轮未验证、未进入目标或阈值，求解器不读取外部箱组、路线和解包。本轮不据此判断胜负。',
              '', '## 测试、保护与复现','',
              f'9项目标/层级/架次独立性/站点标识回归通过；实际执行包另行全量独立核验。{len(original)} 个既存文件逐字节检查，变更数量 {len(changed)}。源码快照、输入打开日志、完整候选、失败尝试均保留。',
              '', '首轮在优化前发现一个旧站点坐标序列化末位差异（约4.7e-10米）导致哈希ID不同。修复为1e-7米容差内唯一匹配既有冻结站点ID，不增加站点或改坐标；旧失败运行与源码保存在diagnostics。修复后使用全新缓存重跑，输出仍需完整独立核验。',
              '', '复现见 REPRODUCE.md；实际轨迹见每个运行的 anchor_trace.jsonl 和汇总 anchor_trace_summary.json。提交于独立开发分支，main保持c13306e。']
    if blockers:lines+=['','## 阻塞项','']+['- '+b for b in blockers]
    (OUT/'GPT_SYNC.md').write_text('\n'.join(lines)+'\n')
    (OUT/'REPRODUCE.md').write_text('''# P1.2 复现

WSL Ubuntu-24.04，仓库 /home/ccc/projects/uav-logistics-comms。
使用本分支源码、原始数据和 .venv；新建独立项目副本，保留基础历史输入。
现有结果禁止覆盖。在复现副本中将随提交的 results/p1_2 改名归档，
创建新的 results/p1_2；重新记录该副本实际存在的历史文件哈希。
原运行保护清单含既存未跟踪文件，因此新副本的保护文件数量可能不同。

```bash
.venv/bin/python - <<'PY'
from pathlib import Path
import hashlib,json
roots=['results','data/raw','docs/paper','src/bench_p1','validation']
files=[p for r in roots for p in Path(r).rglob('*') if p.is_file() and '__pycache__' not in str(p) and not str(p).startswith('results/p1_2/')]
Path('results/p1_2/protected_before.json').write_text(json.dumps({str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files},indent=2))
PY
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python -m unittest src.bench_p1_2.test_driver -v
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python -m src.bench_p1_2.readmission
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python -m src.bench_p1_2.driver --admit
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 .venv/bin/python -m src.bench_p1_2.driver --mode DIAGNOSTIC_WARM --seed 26092511
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 .venv/bin/python -m src.bench_p1_2.driver --mode DIAGNOSTIC_WARM --seed 26092512
.venv/bin/python -m src.bench_p1_2.finish
```

A11重验失败须立即停止，不能继续portfolio或driver。
只有两个开发种子；不读取评价权重。所有新缓存属于对应运行，不能复制旧缓存加速重跑。
短运行由固定请求数量及单LP三秒上限约束，不是正式CPU预算；审计时间单列。
暖启动包重验独立于候选搜索。最后校验旧文件与main未改，重验完整包绑定哈希。
源码修改必须新建诊断运行，不能原地覆盖证据。
''')
    bound=[p for base in [OUT,ROOT/'src/bench_p1_2'] for p in base.rglob('*')
           if p.is_file() and '__pycache__' not in str(p) and p.name!='artifact_manifest.json' and not p.name.endswith('.tmp')]
    write(OUT/'artifact_manifest.json',dict(scope='P1_2_CODE_AND_ALL_RETAINED_EVIDENCE_EXCEPT_THIS_MANIFEST',
          artifact_sha256={str(p.relative_to(ROOT)):digest(p) for p in sorted(bound)}))
    print(status,gate['new_verified_Q3_packages'],blockers)

if __name__=='__main__':main()
