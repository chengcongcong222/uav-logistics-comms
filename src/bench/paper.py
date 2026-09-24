"""Insert measured ablation evidence into the main draft; draw one Q3 counterexample."""
import json,re
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from src.bench.report import ROOT,OUT,table,frontier,vector
from src.q3.e7_pareto import dominates
def main():
    methods=json.loads((OUT/'method_summary.json').read_text());runs=json.loads((OUT/'per_seed.json').read_text())
    import pandas as pd
    points=pd.read_csv(OUT/'all_verified_checkpoints.csv').to_dict('records');paired=[]
    for seed in sorted({r['seed'] for r in runs}):
        a=frontier([r for r in points if r['method']=='POOL' and r['seed']==seed]);b=frontier([r for r in points if r['method']=='POOL_CHALLENGE' and r['seed']==seed])
        paired.append(dict(seed=seed,pool_front_count=len(a),challenge_front_count=len(b),pool_points_strictly_dominated_by_challenge=sum(any(dominates(vector(y),vector(x)) for y in b) for x in a),challenge_points_strictly_dominated_by_pool=sum(any(dominates(vector(y),vector(x)) for y in a) for x in b)))
    (OUT/'paired_archive_comparison.json').write_text(json.dumps(paired,indent=2)+'\n')
    short=table(['方法','最好Jlate','每种子最好Jlate中位数','最好完工/s','最低能耗/kWh','非支配点数中位数','零迟到成功率'],[[m['method'],f"{m['best_J_late']:.3f}",f"{m['median_seed_best_J_late']:.3f}",f"{m['best_makespan']:.3f}",f"{m['best_energy']:.3f}",m['median_per_seed_nondominated_count'],f"{m['zero_lateness_success_rate']:.0%}"] for m in methods])
    z={m['method']:round(m['zero_lateness_success_rate']*5) for m in methods};wins=json.loads((OUT/'verified_challenge_wins.json').read_text())
    mm={m['method']:m for m in methods};covered=sum(r['pool_points_strictly_dominated_by_challenge'] for r in paired);pool_count=sum(r['pool_front_count'] for r in paired);reverse=sum(r['challenge_points_strictly_dominated_by_pool'] for r in paired)
    judgment=f"同预算下，两种模式方法在全部五个种子达到零迟到，uniform LNS未达到。增强法相对普通模式法的最好完工差仅约{abs(mm['POOL']['best_makespan']-mm['POOL_CHALLENGE']['best_makespan']):.6f}秒，最低能耗相同到本表精度，不应放大这一时间尾差。其每种子最好Jnorm中位数由{mm['POOL']['median_seed_best_J_norm']:.6f}降至{mm['POOL_CHALLENGE']['median_seed_best_J_norm']:.6f}；在同种子档案配对中，增强法支配普通模式法累计{pool_count}个档案点中的{covered}个，反向为{reverse}个。点数是五次有限档案的累计，并非独立测试实例数量。当前证据支持本实现的预算效率和辅助交付改善，不支持全指标或全问题的普遍优势。"
    body=f'''本节仅比较三个具体Q2实现：修正后的uniform LNS、模式池加联合整数调度、模式池加主动支配挑战。每法5个种子，统一180秒单核进程CPU上限。初始数据表、几何、评价、资源和共同B0生成规则一致，不导入现成解；数据读取、模式生成、建模、求解和结果导出计入预算，公共几何预处理及独立验证不计入。方法按种子轮换物理核心，只有截止前完整保存且经独立验证的执行包参与统计。

{short}

最好完工与最低能耗分别取独立极值，不能合成为一条方案。非支配点数为每种子去重后有限档案点数的中位数。由于三法共同重新生成可行B0，同时报告零迟到成功率，避免把初始化已有可行解误当作优化能力。

模式法与增强法分别在{z['POOL']}/5、{z['POOL_CHALLENGE']}/5个种子中达到零迟到；uniform LNS为{z['LNS']}/5。本结果反映本实现、实例和预算下的差异，不代表对全部元启发式方法的优劣判断。增强法在本轮另找到{len(wins)}个经过独立验证的Q2支配见证；这与先前7个Q3反例是两套独立统计。主动挑战会占用原本可用于模式生成的预算，因此不能仅凭反例数量推断整体前沿一定更好。

配对有限档案比较另记录每个种子中两法的相互支配覆盖，全部原始结果、逐种子表和计时记录随文保留。不声称本次Q2实验验证了Q3同步结构重构的性能优势，也不据五个种子推导多实例或全局最优结论。

{judgment}

![五种子CPU预算与质量曲线](../../results/ablation180_v2/cpu_anytime.png)

计时校准中第一版监控读数与备用CPU限制触发不一致，整批作废；修正后全部15次从头重跑，未根据结果选择种子或延长某法预算。正式计时采用与子进程相同的POSIX进程CPU时钟，最大观测误差控制在0.2秒内。
'''
    p=ROOT/'docs/paper/G2_PAPER_MAIN_DRAFT.md';text=p.read_text();text=re.sub(r'<!-- ABLATION_BEGIN -->.*?<!-- ABLATION_END -->','<!-- ABLATION_BEGIN -->\n'+body+'\n<!-- ABLATION_END -->',text,flags=re.S)
    text=text.replace('> 正文工作稿。基础模型、Q1—Q4主结果已对应统一几何下的执行包；等CPU五种子实验由配套脚本插入。','> 正文工作稿。基础模型、Q1—Q4主结果及180秒CPU五种子实验均已对应验证证据。')
    p.write_text(text)
    base=ROOT/'results/reset/q3/A11/solutions';a=json.loads((base/'A11_Q3_003/witness.json').read_text())['metrics'];b=json.loads((base/'A11_Q3_003_CC/witness.json').read_text())['metrics']
    fig,axes=plt.subplots(1,3,figsize=(10.4,3.7),layout='constrained')
    for ax,key,label in zip(axes,['J_late','joint_makespan_s','total_energy_kwh'],['Weighted tardiness','Joint completion (s)','Total energy (kWh)']):
        vals=[a[key],b[key]];ax.bar(['Original','Challenge'],vals,color=['#b9c3ca','#267caf']);ax.set_ylabel(label);ax.set_ylim(0,max(vals)*1.2)
        for i,v in enumerate(vals):ax.text(i,v+max(vals)*.025,f'{v:.3f}',ha='center',fontsize=9)
        ax.grid(axis='y',alpha=.2)
    fig.suptitle('Verified Q3 dominance counterexample: A11_Q3_003 → A11_Q3_003_CC')
    for ext in ['png','pdf','svg']:fig.savefig(OUT/f'q3_dominance_example.{ext}',dpi=180)
    p=OUT/'q3_dominance_example.svg';p.write_text('\n'.join(x.rstrip() for x in p.read_text().splitlines())+'\n');plt.close(fig)
    p=ROOT/'docs/paper/G2_PAPER_MAIN_DRAFT.md';text=p.read_text();needle='### 4.4 联合主例与运输层对照'
    if 'q3_dominance_example.png' not in text:text=text.replace(needle,'![一个独立验证的Q3支配反例](../../results/ablation180_v2/q3_dominance_example.png)\n\n'+needle)
    p.write_text(text)
    sync=f'''# 等CPU五种子实验与论文交接

本轮只完成最后一组Q2算法比较，并转入论文收敛；正式G2主例、Q4和提交工作簿未替换。协议为每法180秒单核CPU上限、5种子，共15次。计入输入读取、共同B0、模式生成、建模、求解、保存；独立验证不计时。初版计时不一致的整批数据已作废，V2全部重跑，未挑结果保留。

{short}

模式法与增强法的零迟到成功数为{z['POOL']}/5、{z['POOL_CHALLENGE']}/5，LNS为{z['LNS']}/5。增强法新增{len(wins)}个已验证Q2支配反例，与既有7个Q3反例分开计数。最低能耗与最快完工是不同分量的极值，不能拼成不存在的解。点数区分单次中位数、跨种子并集及旧G2正式档案。

方法结论限于这三个Q2实现、一个实例和180秒预算，不泛化到全部LNS/MILP家族，不宣称验证了Q3同步结构重构优势。增强法要同时看新增反例与模式搜索机会成本；配对档案相互支配见 paired_archive_comparison.json。

本轮裁定：{judgment}

论文正文工作稿已按四层模型完成，并插入本次实验结果。主张—证据表明确：A03/A11在Q2中本来存在权衡，不能说所有目标排序反转；7个Q3支配源点不必原来全属非支配集；14个G2非支配点含8自主+6外部。旧Γ=4认证不转移到新主例。

新Gate：G2_MAIN_PRESERVED_Q2_EQUAL_CPU_FIVE_SEEDS_VERIFIED。strict_equal_cpu_multiseed_comparison_completed=true的范围仅为Q2；Q3多种子算法比较仍未完成。原G2数学结果与工作簿逐字节保留，旧Gate按4ae3d2d版本解释，不篡改其历史false字段。

后续停止算法扩展。剩余为正式参考文献与相关工作、比赛排版/篇幅、图表编号和最终逐表审计；正文工作稿不是已提交论文。入口：[消融报告](ABLATION_REPORT.md)、[逐种子](per_seed.csv)、[新Gate](gate.json)、[论文正文](../../docs/paper/G2_PAPER_MAIN_DRAFT.md)、[证据对照](../../docs/paper/G2_EVIDENCE_MAP.md)。
'''
    (OUT/'GPT_SYNC.md').write_text(sync)
    p=OUT/'ABLATION_REPORT.md';text=p.read_text();text=re.sub(r'<!-- INTERPRETATION_BEGIN -->.*?<!-- INTERPRETATION_END -->','',text,flags=re.S).rstrip();p.write_text(text+'\n\n<!-- INTERPRETATION_BEGIN -->\n## 本轮裁定\n\n'+judgment+'\n<!-- INTERPRETATION_END -->\n')
    print('PAPER_MAIN_DRAFT_AND_HANDOFF_READY')
if __name__=='__main__':main()
