"""Independent audits, predeclared metrics and transparent multi-seed summaries."""
import hashlib,json,math,sys
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'validation/mathematical'))
from xb1_validate import check_package
from src.q3.e7_pareto import dominates
OUT=ROOT/'results/ablation180_v2'
def write(p,v):p.write_text(json.dumps(v,indent=2,allow_nan=False)+'\n')
def vector(m):return dict(J_late=m['J_late'],J_norm=m['J_norm'],joint_makespan_s=m['makespan'],total_energy_kwh=m['energy'],transport_sorties=m['sorties'],relay_sorties=0)
def unique(rows):
    keys=set();out=[]
    for r in rows:
        key=tuple(round(r[k],digits) for k,digits in [('J_late',4),('J_norm',9),('makespan',6),('energy',8),('sorties',0)])
        if key not in keys:keys.add(key);out.append(r)
    return out
def frontier(rows):
    rr=unique(rows);return [r for i,r in enumerate(rr) if not any(i!=j and dominates(vector(q),vector(r)) for j,q in enumerate(rr))]
def table(headers,rows):return '\n'.join(['| '+' | '.join(headers)+' |','|'+'|'.join(['---']*len(headers))+'|']+['| '+' | '.join(str(x) for x in r)+' |' for r in rows])
def main():
    protocol=json.loads((OUT/'protocol.json').read_text());runs=json.loads((OUT/'run_status.json').read_text());assert len(runs)==15
    g=pd.read_csv(ROOT/'results/reset/geometry/route_geometry.csv');flat=[];summary=[];failure=[];byrun={};wins=[]
    for run in sorted(runs,key=lambda x:x['run']):
        d=OUT/run['run'];config=json.loads((d/'config.json').read_text());checkpoints=json.loads((d/'checkpoints.json').read_text());accepted=set(run['accepted_checkpoints']);rr=[]
        for row in checkpoints:
            if row['pid'] not in accepted:continue
            assert row['cpu_ready_s']<=protocol['cpu_budget_s'];p=d/'q2/pareto_schedules'/row['pid']
            try:
                if (p/'validation.json').exists():
                    a=json.loads((p/'validation.json').read_text());assert a['status']=='XB1_Q2_INDEPENDENTLY_VALIDATED'
                    for name,h in a['artifact_sha256'].items():assert hashlib.sha256((p/name).read_bytes()).hexdigest()==h
                else:a=check_package(p,row['pid'],g)
            except Exception as exc:failure.append(dict(run=run['run'],pid=row['pid'],error=str(exc)));continue
            r=dict(run=run['run'],method=config['method'],seed=config['seed'],pid=row['pid'],origin=row['origin'],source=row['source'],cpu_ready_s=row['cpu_ready_s'],**{k:row['metrics'][k] for k in ['J_late','J_norm','makespan','energy','sorties']});rr.append(r);flat.append(r)
        byrun[run['run']]=rr;nd=frontier(rr);best=min(rr,key=lambda r:(r['J_late'],r['J_norm'],r['makespan'],r['energy'])) if rr else None
        zero=[r for r in rr if r['J_late']<=1e-4]
        summary.append(dict(run=run['run'],method=config['method'],seed=config['seed'],core=run['core'],observed_cpu_s=run['observed_process_cpu_s'],wall_s=run['wall_s'],valid_checkpoints=len(rr),unique_checkpoints=len(unique(rr)),nondominated_points=len(nd),feasible_success=bool(rr),zero_lateness_success=bool(zero),best_J_late=best['J_late'] if best else None,best_J_norm=best['J_norm'] if best else None,best_makespan=min(r['makespan'] for r in rr) if rr else None,best_energy=min(r['energy'] for r in rr) if rr else None,zero_late_best_makespan=min(r['makespan'] for r in zero) if zero else None,zero_late_best_energy=min(r['energy'] for r in zero) if zero else None,frontier_ids=[r['pid'] for r in nd]))
        lookup={r['pid']:r for r in rr}
        for r in rr:
            if r['origin']=='ACTIVE_DOMINANCE_MILP':
                assert r['source'] in lookup and dominates(vector(r),vector(lookup[r['source']]))
                wins.append(dict(run=run['run'],source=r['source'],challenger=r['pid'],before=lookup[r['source']],after=r))
    write(OUT/'audit_failures.json',failure);assert not failure,failure
    write(OUT/'per_seed.json',summary);write(OUT/'verified_challenge_wins.json',wins);pd.DataFrame(flat).to_csv(OUT/'all_verified_checkpoints.csv',index=False);pd.DataFrame(summary).to_csv(OUT/'per_seed.csv',index=False)
    methods=[]
    for method in protocol['methods']:
        ss=[r for r in summary if r['method']==method];rr=[r for r in flat if r['method']==method];z=[r for r in rr if r['J_late']<=1e-4]
        methods.append(dict(method=method,seeds=len(ss),best_J_late=min(r['J_late'] for r in rr),median_seed_best_J_late=float(np.median([r['best_J_late'] for r in ss])),best_makespan=min(r['makespan'] for r in rr),best_energy=min(r['energy'] for r in rr),median_per_seed_nondominated_count=float(np.median([r['nondominated_points'] for r in ss])),union_nondominated_count=len(frontier(rr)),feasible_success_rate=sum(r['feasible_success'] for r in ss)/len(ss),zero_lateness_success_rate=sum(r['zero_lateness_success'] for r in ss)/len(ss),zero_late_best_makespan=min(r['makespan'] for r in z) if z else None,zero_late_best_energy=min(r['energy'] for r in z) if z else None,verified_dominance_wins=sum(w['run'].rsplit('_',1)[0]==method for w in wins),median_actual_cpu_s=float(np.median([r['observed_cpu_s'] for r in ss]))))
    write(OUT/'method_summary.json',methods);pd.DataFrame(methods).to_csv(OUT/'method_summary.csv',index=False)
    for m in methods:
        m['median_seed_best_J_norm']=float(np.median([r['best_J_norm'] for r in summary if r['method']==m['method']]))
    write(OUT/'method_summary.json',methods);pd.DataFrame(methods).to_csv(OUT/'method_summary.csv',index=False)
    poolpairs=[]
    for seed in protocol['seeds']:
        signatures=[]
        for method in ['POOL','POOL_CHALLENGE']:
            pool=json.loads((OUT/f'{method}_{seed}'/'pattern_pool.json').read_text());signatures.append(hashlib.sha256(json.dumps(dict(classes=pool['classes'],patterns=pool['patterns']),sort_keys=True).encode()).hexdigest())
        poolpairs.append(dict(seed=seed,identical_generated_pool=signatures[0]==signatures[1],signatures=signatures))
    write(OUT/'paired_pool_checks.json',poolpairs)
    values=lambda x:'—' if x is None else f'{x:.3f}'
    main_table=table(['方法','最好Jlate','每种子最好Jlate中位数','最好完工/s','最低能耗/kWh','每种子非支配点数中位数','可行成功率','零迟到成功率'],[[m['method'],values(m['best_J_late']),values(m['median_seed_best_J_late']),values(m['best_makespan']),values(m['best_energy']),m['median_per_seed_nondominated_count'],f"{m['feasible_success_rate']:.0%}",f"{m['zero_lateness_success_rate']:.0%}"] for m in methods])
    zero_table=table(['方法','零迟到方案最好完工/s','零迟到方案最低能耗/kWh','已验证新增支配见证'],[[m['method'],values(m['zero_late_best_makespan']),values(m['zero_late_best_energy']),m['verified_dominance_wins']] for m in methods])
    per_table=table(['方法','种子','CPU/s','最好Jlate','最好完工/s','最低能耗/kWh','非支配点数'],[[r['method'],r['seed'],values(r['observed_cpu_s']),values(r['best_J_late']),values(r['best_makespan']),values(r['best_energy']),r['nondominated_points']] for r in summary])
    text=f'''# 180 秒单核 CPU、五种子 Q2 消融

本轮仅比较 Q2 搜索：uniform LNS、模式池+联合整数调度、模式池+主动支配挑战。每法五种子，每次同一 **180 秒进程 CPU 上限**，单线程、固定一个物理核心；三法并行使用不同物理核心，按种子轮换核心。CPU 型号与拓扑见 protocol.json。相同的是计算上限，不要求提前收敛或预算保护提前退出的程序空耗到最后一毫秒。

计入解释器/导入、冻结G2输入表加载、共同 B0 初始化、模式生成、矩阵建模、搜索与执行包导出；公共G2几何预计算、独立审计和汇总绘图不计入算法预算，不声称每次重跑原始DEM或Excel预处理。父进程每0.01秒读取 POSIX 进程 CPU 时钟（clock_getcpuclockid + clock_gettime），与子进程 process_time 使用同一计量，对达到上限者终止整个进程组；只接受 cpu_ready_s≤180 的完整检查点。软/硬操作系统 CPU 限制在约两倍预算处另作失控保护，单次外部监控允许观测误差≤0.2秒。正常结束前的最后一次检查点不等于总 CPU 消耗，二者分别记录。

协议在正式运行前写入并绑定代码哈希。12秒试运行只检验计时/落盘，不进入统计。第一版180秒监控中 /proc 观测值与 SIGXCPU 保护触发不一致，整批作废并保留，原因未归咎为已证明的 WSL 内核缺陷；改用 POSIX CPU 时钟、扩大备用保护限额后，全部15次从头重跑。没有根据算法优劣筛选种子或延长某一种方法。5个种子为 {protocol['seeds']}。不读入 G2 现成主结果、R 或 XB 结构。

{main_table}

“最好完工”和“最低能耗”是各自独立极值，通常不属于同一个执行方案；不能拼成虚构方案。各方法的基准 B0 从原始数据重新构建，因此“有可行解”是较弱判据，同时报告更有区分度的零迟到成功率。非支配数按每次运行去重后筛选，再取五次的中位数；所有种子合并的档案点数另见 method_summary.json，不能混用这两种统计。

{zero_table}

## 方法差异与证据范围

LNS 使用修正后的均匀破坏/修复算子，允许10%概率接受非改进，每四轮显式随机排序；记录每个完成的可行候选。没有声称它是带学习权重的自适应 ALNS，也不能把这一个具体 LNS 实现代表全部路线元启发式。

两种模式方法都重新生成有限模式池。初始按6600/7200/9600秒零迟到完工预算和12000秒软迟到预算循环；单次 MILP 内部最多14秒墙钟，外部统一限制总进程 CPU。显式种子用于模式排列、HiGHS随机参数及挑战任务顺序。增强法在100秒 CPU 后，把未挑战的当前档案点送入固定箱组/路线/机型、自由同型资源与连续时刻的支配 MILP，原方案通过资源重编号包含在该域；所有标量均不劣约束下寻找改进。无目标可挑战时继续生成新模式方案。

配对生成池一致性：{sum(x['identical_generated_pool'] for x in poolpairs)}/5 对，完整签名见 paired_pool_checks.json。方法差异含增强法把预算分给挑战所产生的机会成本。找到支配者只能证明相应原点被改进；没找到不能证明非支配，更不能把这次 Q2 实验写成 Q3 同步结构重构的性能消融。

本轮预算内完整检查点 {len(flat)} 个，全部经独立物理、逐箱、时限、类型资源、SOC、充电和航迹核验；主动挑战新增 {len(wins)} 个经过独立验证的支配见证。原 G2 的21个Q3执行包和7个Q3支配反例不计入此处样本。正式 A11_Q3_001、Q4 和提交表保持原方案，不因新 Q2 实验自动替换。

{per_table}

结果只支持本实例、已声明的三个实现、五个种子与180秒 CPU 预算内的比较；没有多实例推广、全局 Pareto 证明或完整算法家族排名。五个种子的最好值必须与中位数和逐种子表同时展示。是否强调算法优势应由本表决定，不预设增强法一定胜出。

![计时与质量曲线](cpu_anytime.png)

下一阶段停止算法扩展，按统一基础模型、Q1/Q2运输优化、Q3通信协同、Q4独立分区四层组织论文；依赖重构作为机制，主动挑战作为有实际反例支持的改进检查。旧鲁棒性只作旧结构历史证据，不继承到当前主例。
'''
    (OUT/'ABLATION_REPORT.md').write_text(text)
    fig,axes=plt.subplots(1,2,figsize=(10.5,4.3),layout='constrained');colors={'LNS':'#b65a3b','POOL':'#287caf','POOL_CHALLENGE':'#38905b'}
    grid=np.arange(5,181,5)
    for method in protocol['methods']:
        curves=[]
        for seed in protocol['seeds']:
            rr=byrun[f'{method}_{seed}'];curves.append([min((x['J_late'] for x in rr if x['cpu_ready_s']<=t),default=np.nan) for t in grid])
        array=np.array(curves);median=np.nanmedian(array,axis=0);q1=np.nanpercentile(array,25,axis=0);q3=np.nanpercentile(array,75,axis=0)
        axes[0].step(grid,median,where='post',color=colors[method],label=method);axes[0].fill_between(grid,q1,q3,step='post',alpha=.13,color=colors[method])
    axes[0].set(xlabel='Process CPU consumed (s)',ylabel='Best weighted tardiness',title='Median and IQR of five seeds');axes[0].set_yscale('symlog',linthresh=1);axes[0].grid(alpha=.2);axes[0].legend(fontsize=7)
    for j,method in enumerate(protocol['methods']):
        ss=[r for r in summary if r['method']==method];axes[1].scatter([j+(i-2)*.045 for i in range(5)],[r['observed_cpu_s'] for r in ss],color=colors[method])
    axes[1].axhline(180,color='black',linestyle='--',linewidth=1);axes[1].set_xticks(range(3),protocol['methods'],rotation=12);axes[1].set(ylabel='Observed total process CPU (s)',title='External enforcement of equal CPU caps');axes[1].grid(alpha=.2)
    for ext in ['png','pdf','svg']:fig.savefig(OUT/f'cpu_anytime.{ext}',dpi=180)
    p=OUT/'cpu_anytime.svg';p.write_text('\n'.join(x.rstrip() for x in p.read_text().splitlines())+'\n');plt.close(fig)
    print('BENCHMARK_AUDITED',len(flat),'CHALLENGE_WINS',len(wins));print(main_table)
if __name__=='__main__':main()
