"""Certified robustness level and common-budget achievable cost indices."""
from src.q3.e8_search import *
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

def generate():
    family=read(OUT/'pareto_family.csv');comparison=read(OUT/'common_absolute_budget_comparison.csv')
    gamma_cert=float(family.Gamma_C_db.max());costs=[]
    for gamma in [0,2,4]:
        part=comparison[(comparison.Gamma_C_db==gamma)&(comparison.J_late_budget==1000000)]
        t=part[part.objective=='makespan'].iloc[0];e=part[part.objective=='energy'].iloc[0]
        costs.append(dict(Gamma_C_db=gamma,C_T_s=float(t.delta),C_E_kwh=float(e.delta),time_percent=float(t.percent_change),energy_percent=float(e.percent_change),
            time_witness=t.solution_id,energy_witness=e.solution_id))
    d4=json.loads((gamma_dir(4)/'demand_summary.json').read_text());d6=json.loads((gamma_dir(6)/'demand_summary.json').read_text())
    difference=d6['guarded_service_sum_s']-d4['guarded_service_sum_s']
    record=dict(Gamma_C_cert_db=gamma_cert,definition='MAX_TESTED_GAMMA_WITH_FOUND_AND_INDEPENDENTLY_VALIDATED_COMPLETE_EXECUTION',
        tested_Gamma_C_db=[0,2,4,6],true_maximum_feasible_Gamma_unknown=True,J_late_budget=1000000,
        C_T_definition='MIN_MAKESPAN_IN_KNOWN_VALIDATED_BUDGET_ARCHIVE_AT_GAMMA_MINUS_SAME_AT_ZERO',
        C_E_definition='MIN_ENERGY_IN_KNOWN_VALIDATED_BUDGET_ARCHIVE_AT_GAMMA_MINUS_SAME_AT_ZERO',
        different_objective_witnesses=True,global_optimal_robustness_price_proven=False,costs=costs,
        demand_duration_increase_4_to_6_s=difference,demand_duration_increase_percent=100*difference/d4['guarded_service_sum_s'],
        congestion_interpretation='OBSERVED_DIFFICULTY_CLOSING_BOUNDED_RESOURCE_MODELS; NOT_PROVEN_PHYSICAL_DISCONTINUITY_OR_PHASE_TRANSITION')
    write_json(OUT/'robustness_indices.json',record);write_csv(OUT/'robustness_cost_indices.csv',costs)
    fig,left=plt.subplots(figsize=(8,4.6),layout='constrained');right=left.twinx();xx=[r['Gamma_C_db'] for r in costs]
    left.plot(xx,[r['C_T_s'] for r in costs],'-o',color='#2476ad',label='Completion-time cost C_T')
    right.plot(xx,[r['C_E_kwh'] for r in costs],'--s',color='#c55b32',label='Energy cost C_E')
    left.set_xlabel('Additional communication margin Gamma_C (dB)');left.set_ylabel('Completion-time increment (s)',color='#2476ad');right.set_ylabel('Total-energy increment (kWh)',color='#c55b32')
    left.set_xticks([0,2,4,6]);left.set_xlim(-.2,6.5);left.set_ylim(-50,1850);right.set_ylim(-.03,1.1);left.grid(alpha=.2)
    left.axvspan(4.15,6.4,color='grey',alpha=.08);left.text(5.2,650,'6 dB: no witness\ntrue boundary unknown',ha='center',fontsize=9)
    for row in costs[1:]:
        left.annotate(f"+{row['C_T_s']:.0f} s",(row['Gamma_C_db'],row['C_T_s']),xytext=(-5,12),textcoords='offset points',fontsize=9,color='#2476ad')
        right.annotate(f"+{row['C_E_kwh']:.3f} kWh",(row['Gamma_C_db'],row['C_E_kwh']),xytext=(6,-19),textcoords='offset points',fontsize=9,color='#c55b32')
    left.set_title('Achievable robustness costs at a common lateness budget of 1,000,000',fontsize=11)
    handles=left.get_lines()+right.get_lines();left.legend(handles,[x.get_label() for x in handles],loc='upper left',fontsize=8)
    for ext in ['png','pdf','svg']:fig.savefig(OUT/f'certified_robustness_cost.{ext}',dpi=180)
    svg=OUT/'certified_robustness_cost.svg';svg.write_text('\n'.join(x.rstrip() for x in svg.read_text().splitlines())+'\n');plt.close(fig)
    section=f'''\n## 已验证鲁棒等级与代价指标

在本次已测试的 Γ∈{{0,2,4,6}} dB 集合内，定义 ΓC_cert 为已找到且独立验证完整执行方案的最大测试阈值，当前 **ΓC_cert=4 dB**。这不是 ΓC_max，也不证明所有 Γ>4 不可行。运输任务结构、两架中继及六组件库存均不增加。

共同 J_late≤10^6 下，C_T(Γ)=T_best_known(Γ)−T_best_known(0)，C_E(Γ)=E_best_known(Γ)−E_best_known(0)。best_known 限于已验证档案；时间与能耗来自各自见证，不能拼接为一个方案。

![通信安全余量与可实现代价](e8/certified_robustness_cost.png)

连线仅连接已测试离散点，不代表未测试余量的已证曲线。4→6 dB 的按运输任务累计保障时长增加 {difference:.4f} s（{100*difference/d4['guarded_service_sum_s']:.3f}%），却伴随当前有限搜索的资源闭合困难。可以作为“可能的离散资源拥塞效应”讨论；尚不足以把真实系统性能的突变、第三架中继必需或物理相变作为已证结论。新诊断进一步说明区间粒度与时间平移自由度必须纳入解释。
'''
    p=Q3/'E8_ROBUSTNESS_REPORT.md';s=p.read_text();s=s.split('\n## 已验证鲁棒等级与代价指标')[0];p.write_text(s+section)
    p=Q3/'E8_GPT_SYNC.md';s=p.read_text();s=s.split('\n## 本轮新增认证指标')[0];p.write_text(s+f'\n## 本轮新增认证指标\n\nΓC_cert=4 dB（仅指已测试阈值中的完整执行认证等级，真实上限未知）。共同预算 C_T/C_E 与双轴图见 [指标 JSON](e8/robustness_indices.json)、[代价图](e8/certified_robustness_cost.png)。4→6 dB 保障累计时长仅增 {100*difference/d4["guarded_service_sum_s"]:.3f}%，但有限搜索更难闭合，适合作为待验证的离散拥塞机制讨论，不能升级成已证物理突变。\n')

if __name__=='__main__':generate()
