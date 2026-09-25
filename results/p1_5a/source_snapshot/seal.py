"""Gate, exact reproduction commands and self-contained engineering handoff."""
import subprocess
from pathlib import Path
from src.p1_5a.common import *
def main():
    a=read(OUT/'F13_readmission.json');q=read(OUT/'q4/independent_validation.json')
    s=read(OUT/'submission_consistency.json');fire=read(OUT/'paper_source_audit.json')
    assert a['status']=='CURRENT_AUTONOMOUS_MAIN_CANDIDATE'
    assert q['status']==s['status']==fire['status']=='PASSED'
    assert read(OUT/'provenance/incumbent_origin.json')['exact_trip_and_start_match']
    log=(OUT/'source_guard_tests.log').read_text()
    assert 'Ran 7 tests' in log and '\nOK' in log
    mainhash=subprocess.check_output(['git','rev-parse','main'],cwd=ROOT,text=True).strip()
    assert mainhash=='c13306ecbc36933502d1197228e5d80f9f7e40cf'
    changes=subprocess.check_output(['git','diff','--name-status',BASE],cwd=ROOT,text=True).splitlines()
    existing={'M\tresults/q2/q2_battery_calendar.csv','M\tresults/q2/q2_box_delivery.csv','M\tresults/q2/q2_sorties.csv',
              'M\tresults/q2/q2_uav_calendar.csv','D\tresults/q3/relay_candidate_gate_stats_raw.csv'}
    historical=[x for x in changes if not any(x.split('\t')[-1].startswith(prefix) for prefix in ['src/p1_5a/','results/p1_5a/'])]
    assert set(historical)==existing
    write(OUT/'protection_check.json',dict(status='PASSED',base_commit=BASE,main_commit=mainhash,
       tracked_historical_changes_equal_initial_state=True,preexisting_changes=sorted(existing),
       enforcement='Readmission/Q4/workbook runtime hooks only permit result writes under results/p1_5a; source edits only src/p1_5a',
       limitation='Git delta and restricted write paths verified; prohibited historical solution files were not opened to compute fresh content hashes'))
    gate=dict(status='P1_5A_F13_MAIN_CHAIN_READY',base_commit=BASE,main_candidate='F13',
       main_candidate_status='CURRENT_AUTONOMOUS_MAIN_CANDIDATE',independent_readmission=True,
       fixed_task_Q4_complete=True,partition_blocks=q['blocks'],partitions=q['partitions'],
       workbook_readback_passed=True,workbook_sheets=s['checked_sheets'],publication_source_guard_passed=True,
       source_guard_tests=7,source_whitelist_entries=fire['whitelist_entries'],
       main_branch_modified=False,historical_files_rewritten=False,
       new_optimization_experiments=False,pattern_pool_changed=False,global_optimality_proven=False,
       complete_pareto_front_proven=False,V02_manuscript_written=False,
       historical_human_reasoning_independence_proven=False)
    write(OUT/'gate.json',gate)
    m=a['metrics'];cfg=read(OUT/'q4/config.json')
    table=[]
    for r in sorted(q['representatives'],key=lambda x:(x['k'],0 if x['partition_id'] in cfg['selected'] else 1)):
        role='缺口优先' if r['partition_id'] in cfg['selected'] else '均衡优先'
        shortage='，'.join(k+'+'+str(v) for k,v in r['shortage'].items() if v)
        table.append(f"|{r['k']}|{role}|{r['partition_id']}|{r['total_shortage_units']}|{r['workload_cv']:.6f}|{shortage}|")
    report=f"""# P1.5-A：F13正式准入、Q4重算与自主证据链冻结

Gate：P1_5A_F13_MAIN_CHAIN_READY。基于 {BASE}，开发分支 p1-5a-f13-main-chain。未修改 main，未刷新F13，未开展新的求解搜索或正式算法比较。

## 1. F13准入

F13状态为 CURRENT_AUTONOMOUS_MAIN_CANDIDATE。

|指标|重新核验值|
|---|---:|
|J_late|{m['J_late']}|
|J_norm|{m['J_norm']:.12f}|
|联合完工/s|{m['joint_makespan_s']:.9f}|
|联合完工/min|{m['joint_makespan_s']/60:.9f}|
|运输能耗/kWh|{m['transport_energy_kwh']:.9f}|
|中继能耗/kWh|{m['relay_energy_kwh']:.9f}|
|总能耗/kWh|{m['total_energy_kwh']:.9f}|
|运输/中继架次|24 / 3|
|通信附加余量/dB|0|

逐项检查冻结2903模式池哈希、模式的物理值与货箱等价类，按原顺序重新核对24架次的箱组分配；F13箱组及起始时刻与保存的自主CP候选完全一致。T01提示解配置及A11自主提示的模式池归属一并核查。三个使用站点均可追溯到本项目早期自主候选池，未导入新站点或其他方案结构。

240条G2地形航段用独立原生DEM行带裁剪重新计算通过。新验证入口只加载F13轨迹，避免旧验证器自动附带无关历史轨迹。全航程独立验证检查69003个采样点，硬约束违例和通信未覆盖点均为0；运输机、电池、中继机与能源组件的身份、时刻、充电/周转和占用冲突均通过原独立算式检查。

通信证据范围为0.5秒采样、阶段与保障边界，以及0.1秒边界细化，不是解析连续时间证明。准入是可执行主例准入，不是全局最优或完整Pareto证明。

## 2. F13固定任务域Q4

原题要求固定问题三任务与保障关系。本轮明确采用整架中继任务保持完整的解释：同一中继架次关联的服务区属于同一任务组，避免固定的一架中继任务跨组共用。这是明示的固定任务域解释。

形成4个不可拆块：

- S001
- S002、S004、S008、S010、S012、S013、S014
- S003、S005、S007、S009、S011、S015
- S006

K=2枚举7种，K=3枚举6种。第二套检查通过图连通性重建不可拆块，以全部组标签组合再去除组编号置换独立核对分区集合；对全部13种分区以端点事件扫描复核八类资源峰值、组内资源着色、缺口、冗余、工作量及CV。

|组数|规则|代表|缺口件数|工作量CV|分类缺口|
|---|---|---|---:|---:|---|
"""+"\n".join(table)+"""

两组缺口优先需增配C型运输机2架、C型电池2组；三组还需A型运输机3架、A型电池3组，缺口总件数分别为4和10。两组缺口优先把S001单列，三组还把S006单列，因此工作量明显不均衡。均衡优先的缺口分别为17和19件，展示了独立执行与组间均衡的资源代价。

“缺口总件数”不是货币成本。资源冗余定义为分组最低需求之和减不分组最低峰值；库存剩余另列。Q4允许报告缺口，不代表现有库存足以按固定时刻分组独立执行。所有结论仅适用于本轮F13固定任务域。

## 3. 同一主例工作簿

submission/结果提交表_F13_自主主例.xlsx包含官方6页和16页补充，共22页。

Q1沿用G2、rho=0.20自主结果。Q2运输与交付两页明确采用F13最终联合调度的实际时刻，与Q3运输和逐箱交付补充页逐单元格相同；Q2是该主例的运输层可行解，不冒充单独Q2再次求得的最优解。Q3中继、通信保障、运输与中继四类资源日历、Q4两种准则的配置和独立日历均来自同一执行包。

回读核对80箱覆盖、24运输、3中继、每个保障区间、每份资源日历、所有Q4配置、官方表头及主要指标。单位明确为s、kWh、度、m和SOC百分比，分钟另列。不存在旧Q2时刻与新中继或其他主例Q4的拼接。

## 4. 论文来源防护

PAPER_SOURCE_WHITELIST.json逐文件列出路径、SHA256、类别和允许的父来源，依赖图无环，默认拒绝其他来源。新的src/p1_5a/build_paper.py同时使用显式加载检查和进程级文件读取钩子：未列来源、哈希不符、符号链接指向未列来源、绕过加载函数直接读取均被拒绝。7项关键防护测试通过。

旧V0.1全文、数据附录及可扫描图件未发现本轮禁用类别的字面命中，但这不等于完成其全历史来源准入。旧稿与旧构建器整体保留且不获新导出授权；4个二进制图件未作OCR/文本验证，也未进入新导出。

新paper_export仅包含白名单驱动的F13主例证据页与构建记录，不生成V0.2正文。新工作簿及其来源记录扫描通过。历史验证程序或序列化代码的阶段名称不被当作方案数据来源；实际允许数据通过文件路径、哈希、来源记录和本轮重算结果判断。

边界：本轮确认可记录的数据来源、实际文件读取和物理结果；不能通过代码审计证明过去人的思考从未受到未记录信息影响，不作这种无法验证的保证。今后论文与提交数据只从本轮批准入口进入。

## 5. 历史保护与下一阶段

原始数据、模式池、旧结果、旧稿和旧工作簿均未改写。Git历史文件差异与开工时的5项既有变动一致；main提交保持c13306ecbc36933502d1197228e5d80f9f7e40cf。没有为历史受限结果重新打开内容计算哈希。

下一阶段才做P1.5-B：V0.2正文、正式参考文献、Q1安全余量敏感性与科研图表。本轮到提交后停止。
"""
    (OUT/'GPT_SYNC.md').write_text(report)
    commands=[
      "PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -u -m src.p1_5a.readmission",
      "PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -u -m src.p1_5a.q4",
      "PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -u -m src.p1_5a.q4_check",
      "PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -u -m src.p1_5a.submission",
      "PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest src.p1_5a.test_source_guard -v > results/p1_5a/source_guard_tests.log 2>&1",
      "PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -u -m src.p1_5a.firewall freeze",
      "PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -u -m src.p1_5a.build_paper",
      "PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -u -m src.p1_5a.firewall audit",
      "PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -u -m src.p1_5a.seal"]
    fence=chr(96)*3
    repro="""# 复现P1.5-A

环境：WSL Ubuntu-24.04，仓库虚拟环境，Python依赖沿用当前项目；本轮不新增求解器依赖。

从仓库根目录运行完整顺序门禁：
"""+fence+"bash\nPYTHONDONTWRITEBYTECODE=1 .venv/bin/python -u -m src.p1_5a.run\n"+fence+"""

分步命令：
"""+fence+"bash\n"+"\n".join(commands)+"\n"+fence+"""

全部重新计算写入results/p1_5a，不改历史目录。整链复现会更新本轮验证运行时和XLSX容器时间戳，因此文件哈希需重新封存；物理指标、固定分区和工作簿内容应一致。不要将哈希变化当成物理结果变化。

本轮没有随机优化实验。Q4枚举、验证及工作簿构建均为确定性过程。输入与产物SHA256分别见F13_readmission.json、provenance/、PAPER_SOURCE_WHITELIST.json及artifact_manifest.json。

Q4固定整架中继及其保障关系，分组资源必须独立；缺口需要增配而非静默放宽库存。

论文后续构建必须通过src/p1_5a/source_guard.py读取白名单来源，旧results/paper_v01/build_paper.py不在新发布流程中。新增学术依据或V0.2数据须先明确审核加入白名单。
"""
    (OUT/'REPRODUCE.md').write_text(repro)
    snap=OUT/'source_snapshot'
    for p in sorted((ROOT/'src/p1_5a').glob('*.py')):
        target=snap/p.name;target.parent.mkdir(exist_ok=True);target.write_bytes(p.read_bytes())
    files=[p for folder in [ROOT/'src/p1_5a',OUT] for p in folder.rglob('*')
           if p.is_file() and '__pycache__' not in p.parts and p!=OUT/'artifact_manifest.json']
    write(OUT/'artifact_manifest.json',dict(base_commit=BASE,files=hashes(files),count=len(files)))
    print('SEALED',gate['status'],len(files),flush=True)
if __name__=='__main__':main()
