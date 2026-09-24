"""Measured G2 result tables, provenance, bounded-search evidence and handoff."""
import json,math
from pathlib import Path
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from src.reset.geometry import ROOT,OUT,VERSION,write
from src.q3.e7_pareto import dominates
def table(headers,rows):return '\n'.join(['| '+' | '.join(headers)+' |','|'+'|'.join(['---']*len(headers))+'|']+['| '+' | '.join(str(x) for x in row)+' |' for row in rows])
def fmt(v):return f'{v:.6f}' if isinstance(v,float) else v
def main():
    q2=[];q3=[]
    for p in sorted((OUT/'q2/pareto_schedules').iterdir()):
        if (p/'template_status.json').exists():continue
        m=json.loads((p/'metadata.json').read_text());q2.append(dict(id=p.name,line='EXTERNAL_CONTROL' if p.name.startswith('B') else 'OWN_GENERATED',J_late=m['J_late'],J_norm=m['J_norm'],joint_makespan_s=m['makespan'],total_energy_kwh=m['energy'],transport_sorties=m['sorties'],relay_sorties=0))
    for p in sorted((OUT/'q3').glob('*/solutions/*/witness.json')):
        m=json.loads(p.read_text())['metrics'];q3.append(dict(id=p.parent.name,line='EXTERNAL_CONTROL' if p.parent.name.startswith('B') else 'OWN_GENERATED',**{k:m[k] for k in ['J_late','J_norm','joint_makespan_s','total_energy_kwh','transport_sorties','relay_sorties']}))
    front={}
    for name,rows in [('Q2',q2),('Q3',q3)]:
        for line in ['OWN_GENERATED','EXTERNAL_CONTROL','COMBINED']:
            rr=[x for x in rows if line=='COMBINED' or x['line']==line]
            front[name+'_'+line]=[x['id'] for x in rr if not any(dominates(y,x) for y in rr)]
        for x in rows:x['combined_archive_nondominated']=x['id'] in front[name+'_COMBINED'];x['line_archive_nondominated']=x['id'] in front[name+'_'+x['line']]
        pd.DataFrame(rows).to_csv(OUT/f'{name.lower()}_metrics.csv',index=False)
    write(OUT/'archive_frontiers.json',dict(criteria='lexicographic (J_late,J_norm), makespan, energy, transport count, relay count',tolerances=dict(J_late=1e-4,J_norm=1e-9,time_count=1e-6,energy=1e-8),claim='WITHIN_THIS_FINITE_VALIDATED_ARCHIVE_ONLY',frontiers=front))
    budgets=[]
    for p in sorted((OUT/'search_logs').glob('*.json')):
        d=json.loads(p.read_text());budgets.append(dict(experiment=p.stem,status=d.get('status','HEURISTIC'),limit_s=d.get('time_limit_s',d.get('limit_s',60)),actual_solver_or_search_wall_s=d.get('wall_s',d.get('actual_wall_s',d.get('runtime_s'))),domain_dual_bound=d.get('restricted_dual_bound'),domain_mip_gap=d.get('restricted_mip_gap'),scope='RESTRICTED_PATTERN_GRID' if 'variables' in d else 'SEE_RAW_LOG'))
    pd.DataFrame(budgets).to_csv(OUT/'compute_budgets.csv',index=False)
    def rows_table(rows):return table(['方案','来源','Jlate','Jnorm','完工/s','能耗/kWh','运输/中继架次','档案非支配'],[[x['id'],x['line'],fmt(x['J_late']),fmt(x['J_norm']),fmt(x['joint_makespan_s']),fmt(x['total_energy_kwh']),f"{x['transport_sorties']}/{x['relay_sorties']}",x['combined_archive_nondominated']] for x in rows])
    cfg=json.loads((OUT/'q4/config.json').read_text());allq4=json.loads((OUT/'q4/all_partitions.json').read_text());byid={x['partition_id']:x for x in allq4};q4rows=[]
    for role,ids in [('缺口优先',cfg['selected']),('均衡优先',cfg['balanced_alternatives'])]:
        for sid in ids:
            x=byid[sid];q4rows.append([role,sid,x['total_resource_units'],x['total_shortage_units'],fmt(x['workload_cv']),str({k:v for k,v in x['shortage'].items() if v})])
    qt=table(['角色','Q4方案','资源件数','缺口件数','工作量CV','分类型缺口'],q4rows)
    cell=json.loads((OUT/'contained_cell_challenges.json').read_text());cell_attempts=[a for r in cell for a in r['attempts']];equal=[a for a in cell_attempts if a['branch']=='equal_lateness'];won=[r for r in cell if 'challenger' in r]
    challenge_table=table(['被挑战方案','独立验证后的支配者'],[[r['source'],r['challenger']] for r in won])
    report=f'''# 最终几何统一与自主主结果重建

本轮正式计算口径是 `{VERSION}`。自主生成线已产生有竞争力的 Q2 与完整 Q3 执行包；正式主例取 **A11_Q3_001**，Q4 与提交表已按其重建。XB1 保留为历史外部结构审计，新外部对照为 B01/B02，不能把其来源改写为自主发现。

自主主例：Jlate=0，Jnorm=0.467343499，联合完工 **7191.582229 s**，总能耗 **70.464235420 kWh**，25 个运输架次、5 个中继架次；仅使用原有两架中继和六个组件池。它比同几何下 B01 的时间代表更快，但能耗更高，运输架次也多一个；不声称全面胜出。未因 Q3 已有好见证而把结构搜索永久锁死。

## 输入和几何版本

用户提供压缩包 SHA256 为 `43ff4433a4e20d4f91a64e736e55c23c4b2b38f47c1751497be0a928bf9640b8`。内含 54 个文件的清单哈希全部匹配；原件归档在 source/。三个 R 见证首先在其声明的旧几何下核对原给定时刻及资源编号的一一映射，未用重新排程掩盖输入问题：R_FAST、R_BALANCED、R_ENERGY 全部通过。它们是用户提供的 GPT 自编参考，不是本轮自主运行产物。

G0 是旧约 30 m 间隔采样；G1 保持经纬度线段定义、改为完整原生穿格；G2 再单独冻结 UTM 49N（EPSG:32649）平面直线。G0→G1 的最大漏峰差为 10.376129 m；G1→G2 对全部 240 条有向运输航段的最高高程无实质差异（仅浮点尾差）。这是本实例测量结果，不代表两种路径一般等价。

G2 不重投影 DEM：对 UTM 直线反投影求原生像元边界交点，检查所有相触像元；边界两侧、角点四邻域均包含，nodata/出界/非有限值拒绝。沿用 GDAL 原生配准，不再加半像元偏移。生成器使用 Brent 根求解，独立程序使用行带裁剪与二分求根；240 条运输航段一致。中继出返航也使用同口径，并由独立 Q3 检查器重新计算。

边界根与单调性检查仍是数值实现：本地投影段要求两轴单调，生成器有 257 点检查；未声称符号几何证明。无线 LOS 使用既有冻结算法，未将“飞行地形完整穿格”偷换成“全部无线传播采用新的遮挡定义”。新轨迹、通信模板、任务—站点关系、资源方案与独立审计均重新生成并绑定 G2 哈希；没有继承旧几何下的通过标记。

Q1 已重算并独立核验全部 80 箱与 45 个最大安全载荷边界：18 架次，59.130796487 kWh，架次作业时长合计 32776.092677 s。合计时长包含准备、装载、飞行、交接，不是机队完工时间。生成器沿用每服务区完整子集划分 DP；独立检查器验证物理与载荷边界，没有另外声称第二套全局最优证明。

## 自主模式与联合资源排程

`src/reset/patterns.py` 从本地 boxes/nodes/types/UAV/battery 与 G2 几何读取数据，不读取 XB 或 R 的箱组、路线、机型作为种子。箱子只在服务区、质量、体积、硬/软截止及权重全相同的类内等价，输出恢复为 80 个实际箱号。非线性逐段载荷能耗按原公式预计算为模式常量。

单点完整物理枚举得到 1074 个模式；经按机型和能耗/数量/时长/电池占用选取并保留单箱后，留下 296 个单点模式。相邻服务区的有界装载组合，枚举 A/B/C 与双向次序，加入 2607 个两点模式，共 2903 个。模式池不完整；局部重构另允许最多三服务区排列。不得把此有限模式池的松弛界称为原题全局下界。

联合整数模型同时决定模式、数量、开始格点、同型无人机/电池区间容量；之后按实际区间分配资源，并在保持选定资源次序下连续左移。开始格点 120/180 s 是搜索限制，通信审计仍为 0.5/0.25 s。Q2 的零迟到分支使用绝对完工预算 6600/7200/9600 s，另有 12000 s 的软迟到低能耗分支；普通物资期望时刻没有被永久改成硬截止。

{rows_table(q2)}

A03 用 19 架次、60.047645 kWh、8844.595055 s 实现零迟到，并在本轮同几何下支配 B02。A11 的时间更短但能耗更高。AS01 用 18 架次、58.674848 kWh 换取显著软迟到，作为低成本取舍保留。B01/B02 的来源仍是 XB 结构，只有本地时刻和物理重新求解；严格几何下 B01 重新联合排程恢复零迟到，旧敏感性修复产生的 89.26 并非必要代价。

修复普通搜索的删箱/拆分后访问次序保留，并增加显式保留架次排列的入口；此前 XB1 的 C 型遗漏、候选截断与迟到优先修复仍保留。普通基线采用均匀算子选择，应称 uniform LNS，不能包装成已实现自适应权重的 ALNS。

## Q3 重建、结构搜索与主动反例

对自主 A03、A11 和外部 B01、B02 全部重建 G2 轨迹与通信任务。沿用可追溯的旧自有站点坐标库，重新算所有任务—站点关系和中继飞行能耗。相对通信模板以箱组/机型/次序/阶段时间、几何和无线代码签名为键；绝对开始时刻改变只平移模板。所有完整保留执行包仍独立全航程验证。

{rows_table(q3)}

A03 的低能耗运输结构接入通信后出现迟到，说明 Q2 优秀并不保证 Q3 时效同样优秀。A11 则在同一物理与资源口径下实现零迟到闭环。表中的非支配只指这批已验证档案，时效按 (Jlate,Jnorm) 字典序作为一个准则，再与时间、能耗和两类架次比较。

结构重构从实际共享中继的运输架次出发。A03 配置的前三对无满足筛选条件的替代；A11 选中 M005/M008，释放 4 箱归属、机型与访问次序，枚举 15 个子集并得到 3 个局部替代，选择一支 AN01，然后释放全部运输时刻/资源并重建中继分组、站点、架次与组件。原 AN01 已通过完整审计，但未改善主例，并被档案其他方案支配；后续 AN01_Q3_001_CC 改善了该重构点并进入档案非支配集，仍未支配主例。它验证了结构确实可变，尚未证明同步重构有性能优势；不是完整全局结构 MILP，也不是已证明最优的整个大邻域。

初轮 Q2 五点挑战加 AS01 两分支挑战未找到新见证，120/180 s 保守网格不保证包含连续原点；C01 仅证明其受限网格挑战不可行。初轮 Q3 的 66 次尝试只有 3 次包含原点，原因是全跨度按通信功率计能过于保守，因此未把这一轮当作强证据。

随后增加固定通信端点先后关系的连续时间域，在该域内用仿射式精确计算 active/idle 能耗，并检查原点能量相等和约束包含性。本轮 {len(cell)} 个源点、{len(cell_attempts)} 次尝试，其中相同迟到分支 {len(equal)} 次均核验原点包含；严格减少迟到分支按定义排除原点。这轮找到 {len(won)} 个真实支配候选，均需独立审计后纳入档案：

{challenge_table}

这证明主动挑战有实质作用：如 A11_Q3_003 被改进至约 7117.71 s，同时减少迟到且不增能耗。但连续域仍固定了端点顺序、运输结构、站点和中继顺序，资源冲突修复有 5 节点上限；只报告“找到支配见证”或“本轮未找到”，不宣称受限域非支配证明，更不宣称全局 Pareto。挑战产生的新点继承对应搜索域和来源记录，没有额外声称它们无法再被改进。

## Q4 与提交一致性

正式 Q3 主例仍是 A11_Q3_001（自主、零迟到、时间优先）。0.25 s 审计检查 134896 个全航程样本，未覆盖样本数为 0；最小双跳余量约 0.149557 dB。此为数值采样证据，不是连续解析证明，更不是 2/4/6 dB 鲁棒认证。

新 Q4 在主例的固定任务时刻和整中继架次依赖下形成 6 块，K2/K3 分别完整枚举 31/90 个分区；八维资源需求+CV 的非支配分区为 14/27 个。每种资源需求由最大重叠下界与可达的组内着色日历相互核验，独立程序用图遍历、全标号枚举和事件扫描复核。

{qt}

最低缺口 K2 是 A 型运输机1、B 型运输机1；K3 另需 C 型运输机1、C 型电池1。缺口是固定独立分区需要新增的资源，不等同于原 Q3 的共享库存不可执行，也不能沿用旧 Q4 的缺口类型。均衡优先替代一起保留，件数不是货币成本。

完整工作簿 `submission/结果提交表_G2_自主主方案.xlsx` 保留官方六页表头，填入 Q1 18 行、Q2 25 架次和 80 箱、Q3 5 中继架次和 75 个完整通信保障区间、Q4 五组配置行。额外 Q3 运输时刻/交付页必须一起读取，避免用 Q2 时刻拼接 Q3 中继。附资源日历与分类型缺口，独立回读核对源表、覆盖和哈希。这里给出数学结果提交包，未代替用户上传比赛系统。

## 计算预算和证据范围

模式生成约 3.50 s；联合 Q2 每次上限 60 s，A01/A02 约 66.29/62.32 s 超时无见证；A03/A11/A12 实际求解约 35.75/11.40/4.54 s；AS01 约 51.49 s。普通 LNS 在迭代边界检查 60 s 限时，实际耗时 103.34 s，仅完成 2 轮，因此不能写成严格等 CPU 预算、多种子稳定胜出的基准。外部结构各有 60 s 联合排程上限；通信建模、候选、验证时间另计，日志和 `compute_budgets.csv` 留存。

AS01 与 A03 的报告 gap=0 仅限本次模式/格点问题；A11/A12 相对 gap 约 0.00948/0.00458，终止容差为 1%。有多点路线与结构可变的实际见证，但完整四方法、等 CPU、多随机种子的消融尚未完成；本轮不据此签发“同步重构算法显著优于强方法”的创新结论。下一步若做方法实验，应优先补这一项，而非继续对弱旧基线包装大改善率。

历史结果固定在提交 0025d992816ca40dc9db668e5b120f1c5108c156 及各自目录；本轮不重写旧 XB1/E6/E7/E8/Q4 的数值或通过标记。旧 E8 的 Gamma_cert=4 只适用于旧 P01 结构，不移植到 G2 主例；Γ6 和新增 ns-3 均停止。后续主任务是基于新结果写清论文与方法边界，不再以旧结构拥塞推论题目不可避免的迟到。

复核入口：`validation/mathematical/reset_gate.py`；几何、Q1/Q3/Q4、提交表均有单独验证器。搜索与复核的确切命令见 `REPRODUCE.md`。完整指标、档案前沿、预算、结构实验、支配挑战、独立证据和输入哈希均在本目录。
'''
    (OUT/'RESET_REPORT.md').write_text(report)
    sync=f'''# 给 GPT 的前线交接：G2 自主主结果已重建

请先以本目录 gate.json 和 RESET_REPORT.md 为权威，旧 XB1/E7/E8/Q4 作为带版本的历史证据，不再作为当前最佳解或新几何的通过结论。

1. 几何正式统一为 {VERSION}，240 条运输航段独立一致，中继出返航同口径；G0→G1 最大漏峰 10.376129 m，G1→G2 本实例无实质最高高程差。无线 LOS 口径未暗改。
2. 用户提供 R_FAST/R_BALANCED/R_ENERGY 原时刻先交叉验证通过；本轮自主模式生成未把 R 或 XB 固定结构作为输入。1074 单点物理模式中保留296，加2607两点，共2903有限模式。
3. 自主 Q2 A03：零迟到，8844.595055 s，60.047645 kWh，19架次，支配同 G2 的 B02。A11：零迟到，6412.642381 s，67.389620 kWh，25架次。AS01：18架次、58.674848 kWh，但软迟到显著。外部 B01/B02 单独标注。
4. 正式 Q3 A11_Q3_001：零迟到，Jnorm=0.467343499，7191.582229 s，70.464235420 kWh，25T/5R，原资源池闭合；0.25 s 全航程134896样本通过。与外部 B01 时间更快、能耗更高，不能说全面支配。
5. 真实运输—中继依赖驱动的结构重构已经运行：AN01 改变了箱组/访问安排并重建资源闭环，完整验证，但没有改善主例。不要把“接口跑通”写成“创新收益已证明”。
6. 初轮过度保守挑战大多不包含原点，已补固定端点顺序、精确 active/idle 能耗的包含域挑战；{len(won)} 个新候选实际支配原点，全部另行独立审计。A11_Q3_003 可被降到约7117.71 s且减少迟到，说明原档案仍可改进。主例本轮未找到支配者，不是最优证书。
7. 新 Q4 为6个不可拆块，K2/K3枚举31/90个，最低缺口2/4件，类型分别是 A机1+B机1，以及再加C机1+C电池1。与旧Q4数据不同。均衡替代、组内资源日历和独立下界证书齐全。
8. 已有完整官方六页工作簿与Q3运输时刻/逐箱交付补充页；不能混用Q2时刻配Q3中继。新主例没有继承旧Gamma_cert=4。

必须保留的限制：有限模式池、时间格点、限时和节点界；普通LNS只有2轮、实际103.34s，尚非严格等CPU多种子基准；没有全局Pareto证明，没有同步重构优越性的完整消融。全部改进率只允许同G2同口径比较。标准整数规划、四类资源、细采样都不是独立创新点。Γ6/ns-3不再加试。

建议下一步：论文围绕自主生成的完整执行见证、通信耦合的真实取舍、可复核边界证据展开；若补算法实验，优先补等预算消融，而非继续强化旧结果叙事。参见 [完整报告](RESET_REPORT.md)、[指标](q3_metrics.csv)、[前沿范围](archive_frontiers.json)、[新Q4](q4/Q4_REPORT.md)、[提交检查](submission/validation.json)。
'''
    (OUT/'RESET_GPT_SYNC.md').write_text(sync)
    fig,axs=plt.subplots(1,2,figsize=(11,4.5),layout='constrained')
    for ax,name,rows in zip(axs,['Q2','Q3'],[q2,q3]):
        for line,color,marker in [('OWN_GENERATED','#1971a8','o'),('EXTERNAL_CONTROL','#cb6b36','^')]:
            rr=[x for x in rows if x['combined_archive_nondominated'] and x['line']==line]
            ax.scatter([x['joint_makespan_s'] for x in rr],[x['total_energy_kwh'] for x in rr],c=color,marker=marker,label=line,s=45)
            labels={'A11_Q3_001':('A11 main: zero late',(8,10)),'A11_Q3_003_CC':('A11 faster: soft late',(8,-15)),'B01_Q3_002_CC':('B01: zero late',(8,-15)),'A03_Q3_002_CC':('A03 low energy: soft late',(-135,-13)),'AN01_Q3_001_CC':('AN01 reconstruction',(-40,10)),'B02_Q3_002':('B02 low energy: soft late',(-145,-15))}
            for x in rr:
                if name=='Q3' and x['id'] not in labels:continue
                label,offset=labels.get(x['id'],(x['id'],(-30,8) if x['id']=='AS01' else (4,4)))
                ax.annotate(label,(x['joint_makespan_s'],x['total_energy_kwh']),fontsize=7,xytext=offset,textcoords='offset points')
        ax.set(xlabel='Completion time (s)',ylabel='Energy (kWh)',title=name+' finite archive (other objectives also apply)');ax.margins(x=.12,y=.12);ax.grid(alpha=.2);ax.legend(fontsize=7)
    for ext in ['png','pdf','svg']:fig.savefig(OUT/f'own_control_tradeoffs.{ext}',dpi=180)
    p=OUT/'own_control_tradeoffs.svg';p.write_text('\n'.join(x.rstrip() for x in p.read_text().splitlines())+'\n');plt.close(fig)
    print('RESET_REPORT_READY', {k:len(v) for k,v in front.items()})
if __name__=='__main__':main()
