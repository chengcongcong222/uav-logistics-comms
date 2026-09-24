"""Summarize independently validated robustness families and unresolved scope."""
from src.q3.e8_search import *
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

def table(headers,rows):
    return '\n'.join(['| '+' | '.join(headers)+' |','|'+'|'.join(['---']*len(headers))+'|']+['| '+' | '.join(map(str,row))+' |' for row in rows])

def main():
    f=read(OUT/'pareto_family.csv');summaries=[];representatives=[];common=[]
    for gamma,part in f.groupby('Gamma_C_db'):
        best=part.sort_values(['J_late','J_norm']).iloc[0]
        representatives.append(best.to_dict())
        summaries.append(dict(Gamma_C_db=int(gamma),points=len(part),best_J_late=float(best.J_late),best_J_norm=float(best.J_norm),
            minimum_makespan_s=float(part.joint_makespan_s.min()),minimum_energy_kwh=float(part.total_energy_kwh.min()),
            relay_sorties_min=int(part.relay_sorties.min()),relay_sorties_max=int(part.relay_sorties.max())))
    write_csv(OUT/'scenario_summary.csv',summaries);write_csv(OUT/'timeliness_representatives.csv',representatives)
    for budget in [100000.,400000.,1000000.]:
        base=f[(f.Gamma_C_db==0)&(f.J_late<=budget+1e-4)]
        for gamma in [0,2,4,6]:
            eligible=f[(f.Gamma_C_db==gamma)&(f.J_late<=budget+1e-4)]
            for objective,key in [('makespan','joint_makespan_s'),('energy','total_energy_kwh'),('relay_sorties','relay_sorties')]:
                if len(eligible):
                    r=eligible.sort_values([key,'J_late','J_norm']).iloc[0];b=float(base[key].min())
                    common.append(dict(J_late_budget=budget,Gamma_C_db=gamma,objective=objective,status='VALIDATED_WITNESS',solution_id=r.solution_id,
                        value=float(r[key]),baseline_value=b,delta=float(r[key])-b,percent_change=(float(r[key])/b-1)*100))
                else:common.append(dict(J_late_budget=budget,Gamma_C_db=gamma,objective=objective,status='NO_KNOWN_WITNESS_NOT_INFEASIBILITY',solution_id='',value=None,baseline_value=float(base[key].min()),delta=None,percent_change=None))
    write_csv(OUT/'common_absolute_budget_comparison.csv',common)
    colors={0:'#2675b8',2:'#dc8a21',4:'#a4489e'};fig,axes=plt.subplots(1,2,figsize=(11,4.2),layout='constrained')
    for gamma,part in f.groupby('Gamma_C_db'):
        for ax,key,label in zip(axes,['joint_makespan_s','total_energy_kwh'],['Joint makespan (s)','Total energy (kWh)']):
            ax.scatter(part.J_late/1000,part[key],s=34,color=colors[int(gamma)],label=f'Gamma = {int(gamma)} dB ({len(part)} points)',alpha=.85)
            ax.set_xlabel('Weighted lateness (thousand weighted seconds)');ax.set_ylabel(label);ax.grid(alpha=.2)
    axes[0].legend(fontsize=8);fig.suptitle('Validated bounded Pareto families; Gamma = 6 dB: no executable witness found',fontsize=11)
    for ext in ['png','pdf','svg']:fig.savefig(OUT/f'robustness_pareto_families.{ext}',dpi=180)
    svg=OUT/'robustness_pareto_families.svg'
    svg.write_text('\n'.join(line.rstrip() for line in svg.read_text().splitlines())+'\n')
    plt.close(fig)
    rows=[[r['Gamma_C_db'],r['points'],f"{r['best_J_late']:.3f}",f"{r['best_J_norm']:.9f}",f"{r['minimum_makespan_s']:.3f}",f"{r['minimum_energy_kwh']:.6f}",f"{r['relay_sorties_min']}–{r['relay_sorties_max']}"] for r in summaries]
    rows.append([6,0,'未找到','—','—','—','未证明不可行'])
    main_table=table(['ΓC / dB','验证点数','最小已知 J_late','对应 J_norm','前沿最短完工 / s','前沿最低能耗 / kWh','中继架次'],rows)
    representative_table=table(['ΓC','方案','完工 / s','总能耗 / kWh','中继架次','中继占用 / s','活动通信 / s','空闲悬停 / s','使用能量组件'],[[int(r['Gamma_C_db']),r['solution_id'],f"{r['joint_makespan_s']:.3f}",f"{r['total_energy_kwh']:.6f}",r['relay_sorties'],f"{r['relay_occupied_s']:.3f}",f"{r['relay_active_s']:.3f}",f"{r['relay_idle_s']:.3f}",r['used_energy_components']] for r in representatives])
    cost_rows=[]
    for r in common:
        if r['J_late_budget']==1000000 and r['objective'] in ['makespan','energy']:
            cost_rows.append([r['Gamma_C_db'],r['objective'],r['solution_id'] or '无已知见证',f"{r['value']:.6f}" if r['value'] is not None else '—',f"{r['delta']:+.6f}" if r['delta'] is not None else '—',f"{r['percent_change']:+.3f}%" if r['delta'] is not None else '—'])
    cost_table=table(['ΓC','次级目标','选择方案','目标值','相对 Γ0 增量','相对增幅'],cost_rows)
    report=f'''# E8 鲁棒通信预算阶段报告

Gate：**E8_PARTIAL_GAMMA6_UNRESOLVED**。0、2、4 dB 三个场景共 **23 个**方案通过独立执行验证；6 dB 在本次有限搜索内没有取得可执行见证。**不能把 E8 标为全通过，不能把 Γ6 的已知前沿为空等同于真实可行域为空。** 正式 ns-3、Q4 均未开始。

## 已验证结果

{main_table}

不同列的前沿极值可能属于不同方案，不能拼成一个虚构执行方案。Γ0 精确保留 E7 的八个权威点；没有重新搜索 Γ0。这里的前沿均是已知档案的非支配集合，不是全局 Pareto 前沿。

时效优先代表方案的完整资源代价如下：

{representative_table}

全部方案保持 28 个运输架次、同一箱组/访问次序/机型，运输能耗固定为 73.47077585529216 kWh；变化来自运输时刻与资源分配、中继站点/分组/次序。两架中继机和六个能量组件的池容量没有增加，使用组件数也不是“最少必需组件数”的证明。中继占用包含准备、飞行、服务与周转，活动通信按每架中继的服务窗口并集计费，不按客户数重复计算。

## 在同一时效预算下比较鲁棒代价

使用相同绝对 J_late 上限 100000、400000、1000000，对每族分别选最短完工、最低能耗、最少中继架次。下表为共同预算 1000000；它比各场景使用不同相对 ε 锚点更适合横向比较。

{cost_table}

完整表见 [共同绝对预算比较](e8/common_absolute_budget_comparison.csv)。预算内没有已知点的格子只表示搜索未提供见证；不表示该预算数学不可行。表中增量是当前固定模型、资源和有限算法所得方案的可复现代价，不是全局最小必要鲁棒成本。各场景的时效优先点可能在某个次级目标上反而较低，不能据此声称增加 Γ 总能降低能耗或时间。真实可行域随 Γ 增加而收缩，但分别搜索出的有限档案不保证嵌套。

![已验证 Pareto 前沿族](e8/robustness_pareto_families.png)

## 模型边界与需求重建

ΓC 同时约束直连 T–G、接入 T–R、回传 R–G，即正在使用的完整路径各跳均满足 M_C ≥ ΓC。原通信物理中的衰落项不变，Γ 是额外安全余量，没有重复添加衰落。直连余量从正值降为低于 Γ 时同样需要中继；不能仅筛掉 E7 中低余量的中继站点。

从冻结的三维运输航迹按 0.5 s 重建直接链路余量，观测到的 LOS/阈值跨越细分到 0.05 s，缺口外扩 2 s 且截在飞行范围内。Γ2：34 段、22 个运输架次、合计保障区间 15619.09375 s；Γ4：40 段、28 架次、18715.53125 s；Γ6：40 个原始缺口、28 架次、19627.21875 s。Γ6 后续将早期长缺口划为最多 300 s 的原子区间，得到 56 段，Gate 检查其并集与原 40 段完全相同。这个合计是按运输任务累计的保障时长，不能当成中继活动通信时长。

候选表规模分别为 Γ2：72 站点/956 边；Γ4：71/1100；Γ6：91/1423。三个场景每段均有通信候选，所以 Γ6 不是“没有通信站点”。候选集不完备，网格定向搜索不是全 DEM 穷举。每架中继仍只在一个固定站点服务后返回；没有引入多跳、移动伴飞、新 MAC、额外中继或改变运输主结构。

## Γ6 已做的工作与剩余问题

1. 继承 E7 分组、按运输单元/原子区间重分组，并联合处理运输机、电池与中继资源。
2. 对早期任务补充靠近起降点的共同站点，枚举 35 种至多五组的早期兼容分区；证据保存在 `gamma_06/whole_gap_diagnostics/`。
3. 允许早期长缺口内的中继交接，重建 56 段候选并尝试六类分组。
4. 联合选择站点、任务到中继架次的分配和时间，每架中继允许两/三次早期架次；28 个覆盖签名的限时 MILP 都返回所建模型不可行。覆盖签名只保留往返较短的代表，且站点、区间划分、架次数受限，因此这不是原连续问题的不可行证明。

任务级通信覆盖可行，但时序、早期硬截止和两架中继的往返/周转约束尚未闭合。下一步应针对 Γ6 做可行性边界审查或更细的定向交接/站点列生成，而不是修改 Q3 箱组/路线，也不应直接推进正式 ns-3。已有有限模型的 infeasible 与整题 infeasible 必须区分。

## 搜索、验证与复现

Γ2、Γ4 沿用 E7 的 ε∈{{0,1%,2%,5%,10%}} × {{makespan, energy, relay_sorties}} 生成器。时效搜索 4 轮×28 修复，加 3 轮×24；每个 ε 次级目标 2 轮×12。先通过额外限时 MILP 取得鲁棒种子，属于不同于 Γ0 的初始化成本。MILP 按墙钟限时，重新搜索可能得到不同见证；保存见证的 CSV 重建是逐字节确定的。能耗提案用连续活动悬停时长近似排名，正式接受、比较和独立验证使用准确活动并集/空闲悬停能耗。

23 点均从 CSV 独立重算运输物理、箱级硬截止、 typed UAV/电池日历、中继飞行/悬停/能量组件和全航程通信；每点 0.5 s，并显式检查相位/任务端点、把观测边界细化到 0.1 s。三个场景各一个时效代表另作 0.25 s 加密验证，均零硬违例、零采样失联。23 点执行 CSV 全部逐字节重放一致；45 个预算查询通过检查；E6/E7 与冻结输入哈希未变。数值全航程采样仍不等于解析连续时间证明。

```bash
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
.venv/bin/python -m src.q3.e8_replay --check-all
.venv/bin/python validation/mathematical/e8_gate.py
.venv/bin/python -m src.q3.e8_replay --gamma 4 --epsilon .02 --objective energy --output results/q3/e8/generated/g4_e02_energy
# 对生成包重新绑定审计路径：
.venv/bin/python validation/mathematical/e8_validate.py --directory results/q3/e8/generated/g4_e02_energy --step .5
```

从已存候选重新搜索使用模块位置参数：`.venv/bin/python -m src.q3.e8_seed_variants 2`，随后 `e8_pareto 2`、`e8_audit_batch 2`。这些命令会改写该场景，必须重新生成报告、重放及 Gate；不要把历史 Gate 当成新结果的认证。完整模型口径见 [E8 semantics](../../docs/model/Q3_ROBUSTNESS_E8_SEMANTICS.md)。

## 阶段状态

Q1 DONE；Q2 Pareto DONE；Q3 通信物理/中继候选/资源闭环/联合 Pareto DONE（E7）；E8 PARTIAL（Γ0/2/4 已验证，Γ6 未闭合）；ns-3 正式验证 WAIT；Q4 独立分区 WAIT；论文/图表/提交表 WAIT。本阶段只交付 E8 研究图表，未开始最终论文整合。
'''
    (Q3/'E8_ROBUSTNESS_REPORT.md').write_text(report)
    sync=f'''# E8 给 GPT 的前线反馈

当前 Gate 是 **E8_PARTIAL_GAMMA6_UNRESOLVED**，请勿签发 E8 全通过，也勿启动正式 ns-3/Q4。

{main_table}

关键事实：Γ0 八点精确保留 E7；Γ2 五点、Γ4 十点均独立验证；共 23 点全部 0.5 s 全航程通过，三个代表 0.25 s 通过，45 个 ε 查询、23 点逐字节重放通过。原运输箱组/路线/机型、两架中继和六组件资源池不变，E6/E7 哈希不变。

Γ 同时作用于直连与两跳，冻结衰落项不变。提高阈值后新增直连缺口必须重建：Γ2 涉及 22 个运输架次，Γ4/6 涉及全部 28 架次。只过滤 E7 旧候选会漏保障任务。

Γ6 每段已有通信候选（56 原子段、91 站点、1423 边），但没有找到满足硬截止和联合资源的完整见证。已尝试共同站点补充、35 类早期分区、300 s 原子交接、联合站点/分配/时序 MILP；受候选集、交接划分和架次数限制，不能宣称真实不可行。原 40 缺口与 56 子段的保障并集完全相同。

请优先审查 Γ6 的早期任务/往返周转瓶颈及现有限制，决定后续如何形成更强可行性或下界证据。无需再动 Q3 主结构。不要把“Γ6 未找到”翻译成“至少需要第三架中继”——本阶段没有证明这个结论。

{cost_table}

上表均使用共同 J_late≤1000000；空格不是不可行证明。每列次级目标对应各自方案，不能组合极值。相对 ε 锚点随 Γ 变化，不适合单独用来比较鲁棒价格；共同绝对预算表已补齐。

权威入口：[完整报告](E8_ROBUSTNESS_REPORT.md)、[Gate](e8/validation.json)、[前沿族](e8/pareto_family.csv)、[共同预算成本](e8/common_absolute_budget_comparison.csv)、[重放证据](e8/replay_checks.json)、[模型边界](../../docs/model/Q3_ROBUSTNESS_E8_SEMANTICS.md)。Gate 内附结果及代码哈希；所有失败模型与界限均保留。结论只覆盖冻结数值模型及有限搜索；不等于全局最优、完整 Pareto 或连续时间解析证明。
'''
    (Q3/'E8_GPT_SYNC.md').write_text(sync)
    print('REPORT_WRITTEN',len(f),flush=True)

if __name__=='__main__':main()
