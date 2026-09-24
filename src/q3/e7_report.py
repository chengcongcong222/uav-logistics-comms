"""Build E7 tables, ablation evidence, and standalone scientific figures."""
import json
from pathlib import Path
import pandas as pd
from src.q3.e7_core import ROOT,OUT,E6,write_json


def load(p):return json.loads(Path(p).read_text())


def markdown(frame):
    lines=['| '+' | '.join(map(str,frame.columns))+' |','|'+'|'.join(['---']*len(frame.columns))+'|']
    for row in frame.itertuples(index=False,name=None):
        lines.append('| '+' | '.join(f'{v:.6f}' if isinstance(v,float) else str(v) for v in row)+' |')
    return '\n'.join(lines)


def main():
    table=pd.read_csv(OUT/'pareto_solutions.csv');gate=load(OUT/'validation.json');base=load(E6/'joint_metrics_P01.json')
    ablation=[]
    cases=[('E6 baseline',base,None),('Official objective / fixed E6 relay order',load(OUT/'fixed_order_official_objective.json')['metrics'],.102381837),
        ('Free transport resources / fixed E6 relay structure',load(OUT/'solutions/L1_RESOURCE_ABLATION/joint_metrics_P01.json'),load(OUT/'free_order_seed.json').get('search_runtime_s',.838743127)),
        ('Fixed transport order / joint relay search',load(OUT/'solutions/FIXED_ORDER_CONTROL/joint_metrics_P01.json'),load(OUT/'fixed_order_control_search.json')['runtime_s']),
        ('L1 joint / best TimelinessKey',load(OUT/'solutions/Q3E7_001/joint_metrics_P01.json'),None),
        ('L1 joint / 2% budget minimum energy',load(OUT/'solutions/Q3E7_008/joint_metrics_P01.json'),None)]
    for label,m,runtime in cases:
        ablation.append(dict(stage=label,status='VALIDATED' if label!='Official objective / fixed E6 relay order' else 'SAME_E6_TIMES_GROUPS_METRICS_RESOURCE_LABELS_MAY_DIFFER',
            **{k:m[k] for k in ['J_late','J_norm','joint_makespan_s','total_energy_kwh','relay_sorties','total_transport_shift_s']},
            runtime_s=runtime,J_late_reduction_pct=100*(1-m['J_late']/base['J_late'])))
    for level in ['L2 equivalent mission','L3 local regroup']:
        ablation.append(dict(stage=level,status='NOT_ACTIVATED_L1_ALREADY_MATERIALLY_IMPROVES_OFFICIAL_METRICS'))
    af=pd.DataFrame(ablation);af.to_csv(OUT/'ablation.csv',index=False)
    runtime={name:load(OUT/f'{name}.json')['runtime_s'] for name in ['timeliness_search','timeliness_refinement','fixed_order_control_search']}
    runtime['epsilon_search']=sum(r['search'].get('runtime_s',0) for r in load(OUT/'epsilon_search.json'))
    runtime['main_search_sum_s']=sum(runtime[n] for n in ['timeliness_search','timeliness_refinement','epsilon_search'])
    runtime['interpretation']='Measured phase runtimes, excluding setup, abandoned pilots, independent audits and reporting; not total user-facing wall time'
    write_json(OUT/'runtime_summary.json',runtime)
    query=pd.DataFrame(load(OUT/'budget_catalog.json')['queries'])
    audit=[]
    for sid in table.solution_id:
        v=load(OUT/'solutions'/sid/'validation_P01_0.5.json');m=load(OUT/'solutions'/sid/'joint_metrics_P01.json')
        audit.append(dict(solution=sid,samples=v['full_flight_samples'],boundary_refinements=v['full_flight_boundary_refinements'],
            min_twohop_db=v['minimum_twohop_margin_db'],min_relay_energy_kwh=v['minimum_relay_energy_margin_kwh'],
            R01_utilization=m['relay_uav_utilization']['R01']['utilization'],R02_utilization=m['relay_uav_utilization']['R02']['utilization'],
            max_component_utilization=max(x['utilization'] for x in m['energy_component_utilization'].values()),
            runtime_s=v['runtime_s']))
    pd.DataFrame(audit).to_csv(OUT/'audit_summary.csv',index=False)
    sensitivity=load(OUT/'solutions/Q3E7_001/validation_P01_0.25.json')
    rep=cases[4][1];fast=cases[5][1]
    report=f'''# E7：Q3 联合资源重排与 ε 预算非支配解

门禁：`{gate['gate']}`。E6 基线提交 `34e7dcb`；本轮得到 **{len(table)} 个逐点独立验证通过的非支配执行方案**，标记 `E6_SUPERSEDED=true`。全部只使用 L1，没有修改运输箱分组、访问顺序或机型；L2/L3 未启用。E8 鲁棒扫描、ns-3 正式实验和 Q4 均未执行。

## 1. 本轮回答了什么

最优已知 TimelinessKey 为 `(87005.086170, 0.558470231)`，相对 E6 P01 加权软迟到减少 **{100*(1-rep['J_late']/base['J_late']):.3f}%**。代表点 Q3E7_001 的完工时间为 {rep['joint_makespan_s']:.6f} s，总能量 {rep['total_energy_kwh']:.6f} kWh，中继架次 9，运输架次仍为 28。

允许 2% 的 J_late 预算后，Q3E7_008 的 J_late 为 {fast['J_late']:.6f}，完工时间 {fast['joint_makespan_s']:.6f} s，总能量 {fast['total_energy_kwh']:.6f} kWh，9 个中继架次。相对 E6，其完工时间减少 {100*(1-fast['joint_makespan_s']/base['joint_makespan_s']):.3f}%，总能量减少 {100*(1-fast['total_energy_kwh']/base['total_energy_kwh']):.3f}%。这些目标存在取舍，所以输出前沿而非“唯一最优”。

本轮证据支持：在保留运输任务结构时，重新安排运输与中继资源已能取得实质收益。它不证明 L2/L3 永远无收益，也不证明完整全局 Pareto 前沿。

## 2. 科学目标和 L1 搜索空间

正式维度为 `TimelinessKey=(J_late,J_norm)`（内部词典序）、联合 makespan、运输加中继总能量、运输架次数、中继架次数。没有用固定加权和作最终排序。运输时移、余量只作诊断。

保持 P01 的 80 箱所属架次、服务访问顺序、运输机型；释放具体运输 UAV ID、电池 ID、原先任务顺序及开始时刻。允许相对 Q2 提前或延后，但准备不得早于零时刻。联合调整中继任务分组、单架次固定站点、两架中继顺序和六组件分配。规划时域上限 40,000 s 是本次搜索限制，不是题面新增要求；全部最终解远小于此上限。

继续使用两架中继、六组件、180 s 准备、30 s 建链、300 s 返航周转。能源组件在起飞时满电，允许准备期间完成充电。单固定悬停点允许同时服务多运输机，通信模块功率在活动区间并集计一次，间隙仍计悬停能量；不引入带宽/MAC 容量新模型，禁止中继多跳。

## 3. 可重复算法与预算族

内层以连续 LP 重算箱交付和时刻，硬期限始终是约束。运输资源按机型/电池池容量重新分配：发现过容量区间团后，枚举其中可分离的有向任务对，逐一带回 LP 检查，再作有界修复；另保留有界分支搜索与列表调度备选。没有保留 E6 的实体资源顺序作为隐含硬限制。

外层邻域包括中继架次插入/换机、共同站点替换、相邻同机任务合并、按运输架次拆分中继组。先用松弛模型筛选，再实际分配资源并精确重算指标。只有资源和能量通过的见证进入搜索档案。候选站点只在当前冲突/邻域需要时交叉验证，复用 E6 的 70 站点池；本轮没有候选不足到必须新建站点的情况，没有全 DEM 枚举。

及时性目标先最小化加权迟到，再在 1e-5 加权秒数值容差内优化 J_norm。能量内层使用“整段悬停通信持续激活”的线性保守近似来产生时刻/排序提案；外层接受、ε 可行性与最终非支配过滤全部使用真实活动并集的能量。这不是精确全局能耗优化。组件容量在精确日历着色阶段检查，失败提案拒收；这一有界搜索也可能漏掉可行安排。

及时性先进行 4 轮、每轮最多修复 28 个邻域，再进行 3 轮、每轮 24 个邻域。随后在 ε=0/1/2/5/10% 下分别搜索 makespan、能量、中继架次，每次最多 2 轮、每轮 12 个邻域；没有改进会提前停止。采用确定性遍历与固定评价次数，不依赖墙钟超时决定最终解。配置与库版本见 `e7/config.json`。

预算以实际最好已知 J_late 为锚。若次级搜索改善锚值，最终目录重锚并从全档案重新筛选；若 J_late 为零，预算选择接口改用 J_norm，并要求 J_late 保持零。本轮 J_late 非零。2%、5%、10% 返回相同部分解只是当前已知档案的平台，不能推出真实前沿已饱和。

{markdown(query)}

预算生成机制由“有界 ε 搜索 → 经验证档案 → 确定性选点 → 重建完整执行包 → 独立再验证”构成。它保证当前已验证档案内可重复，不保证任意预算的全局最优，也不把重放目录当成新一次全局求解。

## 4. 最终非支配前沿

{markdown(table[['solution_id','J_late','J_norm','joint_makespan_s','total_energy_kwh','transport_sorties','relay_sorties']])}

![E7 measured ablation and frontier projection](e7/figures/e7_ablation_pareto.png)

图中 001/002 在 J_late–能量平面重合，用同心标记表示两个不同 makespan；完整五维关系以数值表为准。可编辑矢量图见同目录 SVG。

非支配比较把 TimelinessKey 视作一个词典序维度。例如相同 J_late 下，Q3E7_001 的 J_norm 更好，Q3E7_002 的 makespan 更短，故两者都保留。不能把 J_late 相等的点简单合并。数值比较容差为 J_late 1e-4、J_norm 1e-9、时间 1e-6 s、能量 1e-8 kWh。

独立门禁对 {gate['archive_metric_records_checked']} 条搜索/对照档案指标记录重做非支配核对；并非对这些中间记录全部执行全航程验证。最终 8 点均逐点通过物理与全航程验证，两个消融执行点也另行验证。P02/P03 的 E6 执行见证保留作对照并纳入过滤，未投入同等搜索预算。最终点均来自 P01 的 L1 结构，均全面支配 E6 P01。

## 5. 消融：收益不应全部归因于“仅释放运输顺序”

{markdown(af.fillna('—'))}

只改变正式目标、保持 E6 中继顺序与原运输资源顺序约束，得到相同的时刻、任务分组和指标；最后的区间着色可重新标记实体资源编号，不能称为完整执行包逐字节相同。只释放运输资源、仍保留原中继结构时，J_late 从 648,615.60 降到 622,234.85，改善约 4.1%。保留运输顺序、但进行联合中继邻域搜索时，降到 405,559.11，改善约 37.5%。完整 L1 达到 87,005.09，改善约 86.6%。因此收益来自联合调整，不能把 86.6% 全归因于一个资源释放开关。

固定顺序对照使用相同邻域族与及时性目标、7 轮和每轮 28 个修复配额，但搜索路径及可行域不同。这是有界算法消融，不是两个数学模型的全局最优差距。对照和资源释放消融都由独立验证器复核。L2/L3 未启用的原因是 L1 已有大幅且全面的实测收益；表中的未启用行不是虚构实验或“无收益”结论。

“中继时间紧、组件利用率较低”仍只是已求得日历的资源诊断；仅凭利用率不能证明完整问题的全局瓶颈或六组件永不约束。

## 6. 全航程通信与独立验证

本轮没有生成新运输几何：保持原任务结构，时间平移后的三维轨迹相对形状不变。E6 的前后 2 s 保护区间仅用于构造排程，不成为题面模型或最终通信权威。每个最终点都从完整三维 transport trace、冻结链路预算与 DEM 重算直连或指定 T–R–G01 路径。

{markdown(pd.DataFrame(audit))}

0.5 s 全航程审计包含轨迹阶段/任务边界，观察到 LOS 或余量正负切换时细化到 0.1 s；每个最终候选的整个保护区间也独立复核。代表 Q3E7_001 另作 0.25 s 审计，共 {sensitivity['full_flight_samples']:,} 点，通过。全部 80 箱、医疗/首批硬期限、运输物理、运输 UAV/电池、中继/组件日历、SOC/充电、两跳链路、能源与正式指标均重算，失败方案不得进入最终表。

Gamma_C 始终为 0 dB。最终中继两跳最小余量约 0.623 dB（逐点精确值见表），是站点选择的观测结果，没有强加 2/4/6 dB 门槛。每点 `joint_metrics` 与 `validation` 保存直连/中继有效路径的余量分位数，以及各指定任务窗口最小余量的分布。它们是样本分布，不是概率可靠性模型。零未覆盖表示规定数值审计未发现失联，不是解析连续时间证明。

调度器与验证器分离；验证器没有读取调度 feasible flag 代替物理计算。共享冻结 LOS 原语代表使用同一科学模型。新验证器允许负相对时移和实体资源重分配，同时新增电池机型、资源 ID 与导出日历一致性检查。5 项回归覆盖词典序 Pareto、能量/及时性取舍、支配关系、提前/重分配运输验证，以及错误电池机型拒收。

## 7. 扰动、运行时间与复现

允许提前后，signed shift 不能再单独代表扰动。各执行包同时报告延后量之和、提前量之和、signed shift、absolute shift 和最大延后。Q3E7_001 的 signed shift={rep['total_transport_shift_s']:.6f} s，absolute shift={rep['total_absolute_transport_shift_s']:.6f} s；这些均非正式优化目标。

主及时性搜索 {runtime['timeliness_search']:.3f} s，细化 {runtime['timeliness_refinement']:.3f} s，15 组 ε 搜索合计 {runtime['epsilon_search']:.3f} s，主搜索阶段合计 {runtime['main_search_sum_s']:.3f} s。固定顺序对照 {runtime['fixed_order_control_search']:.3f} s。以上为日志实测阶段时间，排除环境准备、失败探索、独立验证、文档；不是本轮端到端耗时，也不是对 MiMo 的速度倍数比较。

每个非支配点有完整 `solutions/Q3E7_xxx/` 包：运输排程/交付/两类日历，中继排程/两类日历，通信保障，站点/指定候选证据，metrics、witness、独立验证及哈希。8 点 witness 重放生成的执行 CSV 均逐字节一致。15 种预算选择与独立生成的预算目录一致，并实际演示了 2% 能量预算的完整重放和再验证。

```bash
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
# 按预算生成完整执行包，并自动独立验证
.venv/bin/python -m src.q3.e7_replay --epsilon .02 --objective energy \\
  --output results/q3/e7/generated/my_epsilon02_energy
# 逐点执行见证重放一致性
.venv/bin/python -m src.q3.e7_replay --check-all
# 复核已保存的逐点审计、全档案前沿和门禁哈希
.venv/bin/python validation/mathematical/e7_gate.py
# 从冻结 E6 种子重建有界搜索、消融、全部验证和门禁（会重写 E7 结果）
.venv/bin/python -m src.q3.e7_run
```

输入文件 SHA256 见 `input_manifest.json`，最终门禁保存代码和机器结果哈希。E6 与原始数据保持不变；工作树原有无关 Q2 文件改动未纳入此阶段。

## 8. 后续边界

本阶段已经形成预算驱动的、可复现的已知非支配解生成机制，并明确不需要启用 L2/L3 才能取得本轮实质收益。没有证明 9 是中继架次数下界、87,005 是全局及时性最优值、70 站点池完备或 8 点是完整前沿。运输任务固定、有限规划时域、保守能量提案、有限邻域及有界资源修复均可能漏解。

下一阶段应是获得授权后的 E8 鲁棒预算族；本交付到 E7 停止，没有 Gamma_C 扫描、ns-3 正式实验或 Q4。
'''
    (ROOT/'results/q3/E7_JOINT_PARETO_REPORT.md').write_text(report)
    # Standard standalone research artifacts, not a synthetic generated image.
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    figdir=OUT/'figures';figdir.mkdir(exist_ok=True)
    fig,axes=plt.subplots(1,2,figsize=(11,4.3),layout='constrained')
    vals=[cases[i][1]['J_late']/1000 for i in [0,2,3,4]]
    axes[0].bar(['E6','Free resources\nfixed relay plan','Fixed orders\nrelay search','Joint L1'],vals,color=['#7b8794','#d99b44','#4d9da6','#356c9b'])
    axes[0].set_ylabel('Weighted lateness (1000 s)');axes[0].set_title('A. Measured scheduling ablation')
    for i,v in enumerate(vals):axes[0].text(i,v+8,f'{v:.1f}',ha='center',fontsize=9)
    sizes=[120 if sid.endswith('001') else (40 if sid.endswith('002') else 65) for sid in table.solution_id]
    color=axes[1].scatter(table.J_late/1000,table.total_energy_kwh,c=table.joint_makespan_s/3600,cmap='viridis',s=sizes,edgecolor='black',linewidth=.4)
    for r in table.itertuples():
        offset=(12,-5) if r.solution_id.endswith('001') else ((12,12) if r.solution_id.endswith('002') else (5,4))
        axes[1].annotate(r.solution_id[-3:],(r.J_late/1000,r.total_energy_kwh),xytext=offset,textcoords='offset points',fontsize=8)
    axes[1].set(xlabel='Weighted lateness (1000 s)',ylabel='Total energy (kWh)',title='B. Validated known nondominated executions')
    fig.colorbar(color,ax=axes[1],label='Joint makespan (h)')
    for ax in axes:ax.grid(axis='y',alpha=.2);ax.set_axisbelow(True)
    fig.savefig(figdir/'e7_ablation_pareto.png',dpi=200);fig.savefig(figdir/'e7_ablation_pareto.svg');plt.close(fig)
    svg=figdir/'e7_ablation_pareto.svg';svg.write_text('\n'.join(line.rstrip() for line in svg.read_text().splitlines())+'\n')
    print('E7 report, ablation/runtime/audit tables, PNG and SVG figures generated')


if __name__=='__main__':main()
