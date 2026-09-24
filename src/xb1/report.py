"""XB1 evidence tables, scientific comparison figure and GPT handoff."""
import json
from pathlib import Path
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from src.xb1.audit import ROOT,OUT,write
from src.q3.e7_pareto import dominates

def load(p):return json.loads(p.read_text())
def table(rows,fields):
    lines=['| '+' | '.join(label for key,label in fields)+' |','|'+'|'.join(['---']*len(fields))+'|']
    for row in rows:
        vals=[]
        for key,_ in fields:
            v=row[key];vals.append(f'{v:.6f}' if isinstance(v,float) else str(v))
        lines.append('| '+' | '.join(vals)+' |')
    return '\n'.join(lines)

def main():
    q2=[]
    for pid in ['P01','P02','P03','XB01','XB02']:
        m=load(ROOT/'results/q2/pareto_schedules'/pid/'metadata.json');q2.append(dict(m,solution_id=pid))
    q3=[];old=[]
    for p in sorted((OUT/'q3').glob('XB*/solutions/*/joint_metrics_*.json')):q3.append(load(p))
    for p in sorted((ROOT/'results/q3/e7/solutions').glob('Q3E7_*/joint_metrics_P01.json')):old.append(load(p))
    comparisons=[]
    def d2(a,b):
        aa=dict(J_late=a['J_late'],J_norm=a['J_norm'],joint_makespan_s=a['makespan'],total_energy_kwh=a['energy'],transport_sorties=a['sorties'],relay_sorties=0)
        bb=dict(J_late=b['J_late'],J_norm=b['J_norm'],joint_makespan_s=b['makespan'],total_energy_kwh=b['energy'],transport_sorties=b['sorties'],relay_sorties=0)
        return dominates(aa,bb)
    for a in q2[3:]:
        for b in q2[:3]:comparisons.append(dict(question='Q2',candidate=a['solution_id'],baseline=b['solution_id'],dominates=d2(a,b)))
    for a in q3:
        for b in old:comparisons.append(dict(question='Q3',candidate=a['solution_id'],baseline=b['solution_id'],dominates=dominates(a,b)))
    assert all(x['dominates'] for x in comparisons if x['question']=='Q2')
    assert all(dominates(next(r for r in q3 if r['solution_id']=='XB01_Q3_001'),b) for b in old)
    frontier=[r for i,r in enumerate(q3) if not any(i!=j and dominates(s,r) for j,s in enumerate(q3))]
    pd.DataFrame(q2).to_csv(OUT/'q2_comparison.csv',index=False)
    keys=['solution_id','J_late','J_norm','joint_makespan_s','total_energy_kwh','transport_energy_kwh','relay_energy_kwh','transport_sorties','relay_sorties']
    pd.DataFrame([{k:r[k] for k in keys} for r in frontier]).to_csv(OUT/'q3_frontier.csv',index=False)
    pd.DataFrame(comparisons).to_csv(OUT/'dominance_checks.csv',index=False)
    write(OUT/'selection.json',dict(recommended_Q2='XB01',energy_Q2='XB02',recommended_Q3='XB01_Q3_001',lower_energy_Q3='XB02_Q3_002',Q4='OLD_BASELINE_ONLY_REBASE_REQUIRED',E8='OLD_P01_STRUCTURE_SENSITIVITY_ONLY',new_Q3_robustness_not_certified=True,exact_dem_Q3_not_recomputed=True))
    write(OUT/'config.json',dict(experiment='XB1_EXTERNAL_BENCHMARK_AUDIT',source_commit='98fc5da2eba04d54e8c003f31232f85c17a9ebf5',imported_fields=['box grouping','visit sequence','aircraft type'],external_times_ids_metrics_used_for_scheduling=False,physics='Frozen local authority; exact native-cell lon/lat traversal separately audited as sensitivity',Q2_search=dict(time_limit_per_structure_s=60,requested_mip_relative_gap=.005,objective='makespan with J_late=0 constraints',horizon_s=20000),Q3_search=dict(Gamma_C_db=0,grouping_batches=[8,6,12],stop_after_first_joint_seed=True,seed_time_limit_s=60,neighborhood_rounds=1,repairs_per_objective=8,horizon_s=40000),random_sampling=False,seed=None,blas_threads=1,external_code_executed=False,global_optimum_proven=False))
    fig,axes=plt.subplots(1,2,figsize=(11,4.4))
    for ax,rows,new,title in [(axes[0],q2[:3],q2[3:],'Q2: local-model recomputation'),(axes[1],old,q3,'Q3: independently validated executions')]:
        tk='makespan' if ax is axes[0] else 'joint_makespan_s';ek='energy' if ax is axes[0] else 'total_energy_kwh'
        ax.scatter([r[tk]/3600 for r in rows],[r[ek] for r in rows],marker='x',s=65,color='#777777',label='Previous archive')
        for prefix,color,label in [('XB01','#0072B2','24-sortie external structure'),('XB02','#D55E00','21-sortie external structure')]:
            pts=[r for r in new if r['solution_id'].startswith(prefix)]
            ax.scatter([r[tk]/3600 for r in pts],[r[ek] for r in pts],c=color,s=45,label=label)
        ax.set(xlabel='Completion time (h)',ylabel='Total energy (kWh)',title=title);ax.grid(alpha=.2);ax.legend(fontsize=7)
    fig.text(.5,.01,'Timeliness and resource counts are additional objectives; see CSV tables. No global optimality claim.',ha='center',fontsize=8)
    fig.tight_layout(rect=[0,.04,1,1])
    for ext in ['png','pdf','svg']:
        path=OUT/f'external_benchmark_comparison.{ext}';fig.savefig(path,dpi=180)
        if ext=='svg':path.write_text('\n'.join(line.rstrip() for line in path.read_text().splitlines())+'\n')
    plt.close(fig)
    fields2=[('solution_id','方案'),('J_late','J_late'),('J_norm','J_norm'),('makespan','完工/s'),('energy','能耗/kWh'),('sorties','运输架次')]
    fields3=[('solution_id','方案'),('J_late','J_late'),('J_norm','J_norm'),('joint_makespan_s','联合完工/s'),('total_energy_kwh','总能耗/kWh'),('transport_sorties','运输架次'),('relay_sorties','中继架次')]
    exact=load(OUT/'dem_sensitivity_summary.json')
    text=f'''# XB1 外部基准统一口径审计与 Q3 重建

结论：两套公开运输结构均通过本项目独立审计，且分别支配旧 Q2 P01–P03。重新建立通信任务并完成中继闭环后，9 个 Q3 候选也全部通过独立全航程验证；其中 XB01_Q3_001 支配旧 E7 全部8点。旧解的可行性没有因此被否定，但已不应继续作为最佳已知主结果。

## 来源、复算与归属

外部结构来自 [superZhuMY/UAV-Transport-Comm-2026D](https://github.com/superZhuMY/UAV-Transport-Comm-2026D/tree/98fc5da2eba04d54e8c003f31232f85c17a9ebf5)，固定提交98fc5da2eba04d54e8c003f31232f85c17a9ebf5。来源文件为其审查目录下两份 fixed_route_rescheduled.json；原运行 solution.json 和审查 evidence 同时留档。逐文件 URL、SHA256 见 source/manifest.json。固定树未发现 LICENSE，未复制或运行外部代码；保存的是可核查的公开数值结果，借用箱组/访问次序/机型必须明确署名，不能写成自主搜索发现。

优化输入仅有这三类结构字段。对方的起飞时刻、资源编号、能耗和验证标志均不进入本地排程。采用本地80箱质量体积、原生DEM几何、重力常数9.80665、分段载荷能耗、交接完成送达、31箱硬时限、4/2/2架运输机与6/4/4块运输电池、充满复用等冻结规则，重新求解连续时刻与资源分配。未改变通信或能源物理，也未增加库存。

## Q2：外部信号已成为同口径证据

{table(q2,fields2)}

两套 XB 方案各80箱恰好一次交付，全部硬期限通过，J_late=0。字典序及时性 (J_late,J_norm) 是一个目标；XB02 的 J_norm 不优于旧点，但因 J_late 更小，按冻结定义仍支配旧点。若把 J_norm 改成独立平行目标，就不能沿用这个支配结论。

24架次结构先用旧贪心解码也成功，得到7180.339884 s；本地联合排程进一步得到6489.127320 s。21架次结构通过全部单架次物理门禁，但旧贪心解码返回None；联合排程却成功得到9256.714989 s。这是“解码器失败不等于结构不可行”的直接反例。两次MILP每次预算60 s；XB02以限时可行 incumbent 收尾。XB01的求解器成功状态也仅对应固定结构、零迟到约束和0.5%相对间隙设置，不能说全局运输最优。

## Q3：重新生成任务、候选和资源执行包

XB01重建21个通信保障区间、118站点/952关系；XB02为16区间、118站点/662关系。全部任务有候选。站点几何可从旧库复用，但每条关系针对新轨迹重新计算；没有继承旧保障有效性结论。各自首个分组种子即得到联合见证，随后只进行一轮有限邻域改进。

{table(q3,fields3)}

9点是有限搜索档案中的非支配候选，不是完整Pareto前沿。能耗优先产生的两个40000 s边界点只作探索性权衡，不推荐作为提交主例。推荐主例 **XB01_Q3_001**：零迟到、8214.302952 s、69.731633 kWh、24运输+6中继；低能耗权衡可选 **XB02_Q3_002**：J_late=14285.374353、9353.226490 s、64.785466 kWh、21运输+5中继。二者不能拼接成一个方案。

相对旧时效主例Q3E7_001，新主例迟到由87005.086170降至0，联合完工缩短3830.071884 s（31.800%），总能耗降低9.090529 kWh（11.533%），运输28→24，中继9→6；并支配全部旧E7点。仍只使用2架中继、6个能源组件。

## 独立证据与可复现性

- Q2：独立逐航段质量/体积/能量、80箱及硬期限、typed UAV和battery完整占用/充电检查；每个轨迹顶点逐项重建，重新计算J_late/J_norm。
- Q3：9点全部0.5 s全航程检查，涵盖直连区间、保障边界、两跳链路、中继往返/周转和组件充电。两个及时性代表点另以0.25 s复核，分别130317和111855个样本。继承权威LOS原语，但独立重构轨迹、链路运算、能源、时钟和资源日历；不依赖优化器的成功标志。XB01系列独立保障区间最小两跳余量为0.149557 dB，XB02为0.623084 dB，均满足标准Gamma=0；新主例额外余量较小，不能拿旧结构4 dB认证替代其鲁棒分析。
- 通信结论是含边界细化的数值证据，不是解析连续时间证明。候选站点集合有限，未证明全局最优。
- 2套Q2和9套Q3执行CSV从保存见证重放，逐字节比较，详见 replay_checks.json。6项回归覆盖候选遗漏、排序以及篡改能量/漏箱/轨迹偏移的拒错。

## 新发现：旧“精确DEM”措辞不成立

本仓库冻结 route_geometry.csv 的构建器使用约30 m采样，另有整数栅格行走交叉检查；它并不是严格穿过全部原生栅格单元。XB1新增严格边界事件遍历，并用独立行带裁剪算法对全部240有向航段复核。原规则沿lon/lat线段解释保持不变，不做DEM重采样；本结果不声称解决了投影曲线与经纬度线段之间的一切几何解释问题。最大航段地形漏峰为10.376129 m。

没有暗改旧权威表。将精确穿格高度作为单独敏感性，五套结构全部通过；固定原资源次序且不提前原起飞时刻，修复日历后如下：

{table([dict(r,solution_id=r['pareto_id']) for r in exact],fields2)}

新旧结构在这套更严格口径下的支配关系仍成立。XB01少量软迟到89.255762，不能将冻结口径的零迟到照搬过去。新Q3当前是冻结运输几何下验证的执行方案；**逐格DEM版本尚未重建Q3通信和Q4，不能宣称已经通过**。原生栅格精确化若成为最终正式口径，必须重新生成轨迹、通信任务及后续结果；该动作不能靠替换能耗表完成。

## 旧搜索实现诊断与修复

1. B1对6种跨区合并只取前4个，按A/B/C与双方向顺序，恰好漏掉两种C型跨区合并。已恢复全部机型方向。
2. 新架次插入只产生A/B，C型缺失；候选总表再取前12项，使后续可行插入系统性消失。已取消这两个按列表位置的截断。
3. repair仍用J_time（J_norm别名）优先，与E3.2正式及时性不一致。已改为(J_late,J_norm,makespan,energy,sorties)，regret排序同步。
4. 初始硬箱/软箱分组较刚性，固定紧急度贪心资源解码会漏掉可行排列。新增XB1联合排程已给出直接反例，旧解码器仍为启发式，不能充当结构不可行证书。

这些是代码层面的已验证缺陷/局限；没有运行逐项消融，不能把本次百分比改善归因于某个修复，也没有宣称修复后ALNS已发现同等结果。外部 warm start 的归属仍明确保留。取消截断可能增加旧ALNS单轮耗时，后续应采用物理可行性预筛或结构缓存，不能恢复无依据前缀裁剪。

## 对Q4、鲁棒性和论文的影响

- Q4现有精确分区仍只对应Q3E7_001。更换Q3主例后必须重建服务依赖图、不可拆块和独立资源配置；原K2/K3增配量不能照搬。此轮完成XB1及两套结构的Q3闭环，未覆盖旧Q4执行包。
- E8的0/2/4 dB代价和Gamma_cert=4只针对旧P01运输结构。这些敏感性实验证据继续有效，但新XB结构尚无同级鲁棒认证。不得把旧Gamma_cert或鲁棒代价直接贴给新主例。
- 论文主结果冻结应解除：旧Q2、E7最优性措辞撤下，保留为历史对照；新主例建议XB01_Q3_001，明确外部结构与本地排程、通信闭环的贡献边界。
- 下一步优先固定最终DEM口径并完成新主例的Q4/提交表衔接；Gamma6仍关闭，不再占据主线；ns-3仍为后期可选。

## 复现入口

在仓库根目录设置 OPENBLAS_NUM_THREADS=1、OMP_NUM_THREADS=1、MKL_NUM_THREADS=1。离线来源已按固定提交保存；不需要运行外部仓库代码。

1. .venv/bin/python -m src.xb1.audit（重新求解两套Q2；已验证输出会被重写，随后必须再审计）
2. .venv/bin/python validation/mathematical/xb1_validate.py
3. .venv/bin/python -m src.xb1.dem_sensitivity
4. .venv/bin/python -m src.xb1.q3 XB01；同样对XB02运行。缓存只适用于清单输入不变；改动运输轨迹时必须另建实验目录并重建通信任务，不得复用旧缓存。
5. .venv/bin/python validation/mathematical/xb1_q3_validate.py XB01；XB02同理；代表点增加 --step .25 --representative。
6. .venv/bin/python -m src.xb1.replay
7. .venv/bin/python -m unittest discover -s validation/mathematical -p test_xb1_regressions.py -v
8. .venv/bin/python -m src.xb1.report；.venv/bin/python validation/mathematical/xb1_gate.py

此审计没有验证其他公开仓库的当日进度或所谓“领先”排名；不将提示词中这些二手判断当成本次结论。官方解释未成为此次物理模型改动依据。
'''
    (OUT/'XB1_REPORT.md').write_text(text)
    handoff='''# 给 GPT 的 XB1 前线同步

**需要修正主线判断：外部结构在我们模型下成功，而且已经完成新的Q3闭环。旧Q2候选池和旧E7数值已被改善，不再是最佳已知主结果。**

''' + text[text.index('## Q2：'):text.index('## 复现入口')]+'''\n\n完整来源、复现命令、模型边界见 [XB1_REPORT.md](XB1_REPORT.md)；最终文件哈希和Gate见 gate.json。请据此调整论文叙述，不要继续引用“Q2已足够好”或把旧E8认证直接继承给新结构。下一轮明确处理最终DEM口径及新Q4。\n'''
    (OUT/'XB1_GPT_SYNC.md').write_text(handoff)

if __name__=='__main__':main()
