"""Guarded publication fact sheet, not the P1.5-B V0.2 manuscript."""
from src.p1_5a.source_guard import SourceGuard,ROOT
from pathlib import Path
import json
def main():
    guard=SourceGuard();guard.install()
    facts=guard.json(ROOT/'results/p1_5a/publication_facts.json')
    # Also force readback of the validated workbook status before publication.
    check=guard.json(ROOT/'results/p1_5a/submission_consistency.json')
    assert check['status']=='PASSED'
    m=facts['metrics'];v=facts['validation'];q=facts['q4']
    rows=[]
    for x in q['representatives']:
        shortage='、'.join(k+' +'+str(n) for k,n in x['shortage'].items() if n)
        rows.append(f"|{x['partition_id']}|{x['k']}|{x['total_shortage_units']}|{x['workload_cv']:.6f}|{shortage}|")
    text=f"""# F13 自主主例证据页

本页用于冻结论文与提交表的数据继承关系，不是论文 V0.2 正文。

原始题目与附件 → 自主2903模式池 → F13运输结构 → 轨迹通信任务 → 三次中继 → 独立执行验证 → 固定任务分区。

主例状态：CURRENT_AUTONOMOUS_MAIN_CANDIDATE。

|指标|数值|
|---|---:|
|迟到惩罚|{m['J_late']}|
|归一化交付指标|{m['J_norm']:.9f}|
|联合完工/s|{m['joint_makespan_s']:.6f}|
|联合完工/min|{m['joint_makespan_s']/60:.6f}|
|总能耗/kWh|{m['total_energy_kwh']:.6f}|
|运输架次|{m['transport_sorties']}|
|中继架次|{m['relay_sorties']}|

全航程数值复核 {v['full_flight_samples']} 个检查点，无硬约束违例和通信未覆盖点。采样步长 {v['step_s']} 秒，边界细化至 {v['boundary_refinement_s']} 秒；这不是解析连续时间无线证明。

固定F13箱组、访问顺序、运输与中继时刻和保障关系，形成 {q['blocks']} 个不可拆块。两组完整枚举 {q['partitions']['2']} 种，三组完整枚举 {q['partitions']['3']} 种。任务组独立配置资源，库存缺口必须补足后才可保持原任务时刻独立执行。

|分区方案|组数|缺口件数|工作量CV|分类缺口|
|---|---:|---:|---:|---|
"""+"\n".join(rows)+"""

缺口优先：先最小资源缺口件数，再最小资源配置件数，最后比较工作量CV。均衡优先：先最小无人机占用工作量CV。件数不是货币成本；分组资源冗余与库存剩余分别报告。

工作簿Q2运输表、逐箱交付表与Q3运输补充页使用相同的F13最终实际时刻。Q1沿用G2自主结果，Q4完全继承F13。

结论范围仅为已验证主例及其固定任务域，不声称全局最优或完整Pareto前沿。

下一阶段再完成V0.2正文、正式参考文献、Q1安全余量敏感性与科研图表。
"""
    dest=ROOT/'results/p1_5a/paper_export';dest.mkdir(exist_ok=True)
    (dest/'F13_MAIN_EVIDENCE.md').write_text(text)
    (dest/'BUILD_AUDIT.json').write_text(json.dumps(dict(status='PASSED',sources_read=sorted(guard.accesses),
        all_sources_hash_guarded=True,V02_body_generated=False),ensure_ascii=False,indent=2)+'\n')
    print('GUARDED_PAPER_FACTS_BUILT')
if __name__=='__main__':main()
