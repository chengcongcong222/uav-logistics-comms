"""Single-process, single-core Q2 benchmark worker; only ready checkpoints count."""
import argparse,copy,json,math,os,random,resource,signal,time,warnings
from pathlib import Path

def main():
    ap=argparse.ArgumentParser();ap.add_argument('method',choices=['LNS','POOL','POOL_CHALLENGE']);ap.add_argument('seed',type=int);ap.add_argument('--budget',type=float,default=180);ap.add_argument('--core',type=int,required=True);ap.add_argument('--root',default='results/ablation180');args=ap.parse_args()
    os.sched_setaffinity(0,{args.core});resource.setrlimit(resource.RLIMIT_CPU,(math.ceil(2*args.budget)+1,math.ceil(2*args.budget)+2))
    root=Path(args.root).resolve()/f'{args.method}_{args.seed}';root.mkdir(parents=True,exist_ok=True)
    # Process CPU starts at interpreter launch: imports, preprocessing and export count.
    budget=args.budget;rng=random.Random(args.seed);startwall=time.monotonic();records=[];serial=0
    def write(p,obj):
        tmp=p.with_suffix(p.suffix+'.tmp');tmp.write_text(json.dumps(obj,indent=2,allow_nan=False)+'\n');os.replace(tmp,p)
    def remaining():return budget-time.process_time()
    import numpy as np
    from scipy.optimize import milp as scipy_milp
    from src.reset.geometry import tables,VERSION
    from src.reset import patterns
    from src.xb1.audit import export as physical_export
    from src.q2.evaluator import MissionEvaluator
    from src.q2.scheduler import ResourceDecoder
    from src.q2.initial_solution import build_b0
    from src.q2.evaluator_sol import evaluate_solution
    from src.q2.operators import DESTROY,REPAIR
    from src.q3.e7_pareto import dominates
    from src.bench.challenge import challenge
    warnings.filterwarnings('ignore',message='Unrecognized options detected')
    def limited_milp(*aa,**kw):
        if remaining()<2:raise TimeoutError('CPU budget nearly exhausted before MILP')
        opts=dict(kw.get('options',{}));opts['threads']=1;opts['random_seed']=args.seed
        opts['time_limit']=max(.02,min(opts.get('time_limit',14),14,remaining()*.8));kw['options']=opts
        return scipy_milp(*aa,**kw)
    patterns.OUT=root;patterns.milp=limited_milp
    tab=tables();ev=MissionEvaluator(tab);decoder=ResourceDecoder(tab)
    def convert(m):return dict(J_late=m['J_late'],J_norm=m['J_norm'],joint_makespan_s=m['makespan'],total_energy_kwh=m['energy'],transport_sorties=m['sorties'],relay_sorties=0)
    def save(decoded,tag,origin,source=None):
        nonlocal serial
        if remaining()<.5:raise TimeoutError('No export outside budget')
        serial+=1;pid=f'P{serial:04d}';temporary=root/'partial'/pid;dest=root/'q2/pareto_schedules'/pid
        m=physical_export(decoded,tab,temporary,pid)
        cpu=time.process_time()
        if cpu>budget-.1:raise TimeoutError('Completed package is too close to CPU cutoff')
        dest.parent.mkdir(parents=True,exist_ok=True);os.replace(temporary,dest)
        record=dict(pid=pid,origin=origin,source=source,cpu_ready_s=time.process_time(),wall_ready_s=time.monotonic()-startwall,metrics=m,mission_file=str(dest/'missions.json'))
        records.append(record);write(root/'checkpoints.json',records);print('CHECKPOINT',pid,origin,record['cpu_ready_s'],m,flush=True);return m
    def pattern_export(decoded,_tables,dest,tag):return save(decoded,tag,'PATTERN_JOINT_MILP')
    patterns.export=pattern_export
    write(root/'config.json',dict(method=args.method,seed=args.seed,cpu_budget_s=budget,core=args.core,geometry=VERSION,scope='Q2_ONLY',timing='process user+system CPU, including imports/data/preprocessing/search/export; independent audit excluded',threads=1,initialization='build_b0 from original local data, freshly generated for all methods',external_or_frozen_solution_input=False))
    try:
        base=build_b0(ev,decoder);save(base.decoded,'INITIAL','COMMON_RAW_DATA_B0');best=current=base;iters=0
        if args.method=='LNS':
            key=lambda sol:tuple(sol.metrics[k] for k in ['J_late','J_norm','makespan','energy','sorties'])
            while remaining()>.5:
                d=rng.choice(list(DESTROY));r=rng.choice(list(REPAIR));fn=DESTROY[d]
                ms,loose=fn(current.missions,rng,ev) if d in ['worst_timeliness_removal','related_service_removal'] else fn(current.missions,rng)
                sol=REPAIR[r](ms,loose,rng,ev,decoder);iters+=1
                if sol:
                    if key(sol)<key(best):best=sol
                    # Archive feasible outputs, not only one lexicographic best.
                    save(sol.decoded,'LNS','UNIFORM_DESTROY_REPAIR')
                    if key(sol)<key(current) or rng.random()<.1:current=sol
                if iters%4==0:
                    raw=copy.deepcopy(current.missions);rng.shuffle(raw);sol=evaluate_solution(raw,ev,decoder,preserve_order=True)
                    if sol:
                        save(sol.decoded,'ORDER','EXPLICIT_ORDER_DECODER')
                        if key(sol)<key(best):best=sol
            return
        pool=patterns.build_pool();rng.shuffle(pool['patterns']);write(root/'pool_order_seed.json',dict(seed=args.seed,patterns=len(pool['patterns']),permutation='Python Random(seed).shuffle once; all patterns retained'))
        requests=[(6600,120,True,True),(7200,180,True,True),(9600,180,True,False),(12000,180,False,False)]
        challenged=set();attempts=[];request_no=0
        while remaining()>2:
            # Same initial pool generation/pipeline for both variants; after 100
            # CPU seconds the enhanced method interleaves explicit challenges.
            if args.method=='POOL_CHALLENGE' and time.process_time()>=100:
                candidates=[x for x in records if x['pid'] not in challenged and not any(dominates(convert(y['metrics']),convert(x['metrics'])) for y in records)]
                if candidates:
                    target=min(candidates,key=lambda x:(x['metrics']['J_late'],x['metrics']['J_norm'],x['metrics']['makespan']));challenged.add(target['pid'])
                    tick=time.process_time();answer,info=challenge(target,tab,limited_milp,rng)
                    info.update(source=target['pid'],start_cpu_s=tick,end_cpu_s=time.process_time());attempts.append(info);write(root/'challenges.json',attempts)
                    if answer is not None:
                        m=save(answer,'CHALLENGE','ACTIVE_DOMINANCE_MILP',target['pid']);assert dominates(convert(m),convert(target['metrics'])),(m,target['metrics'])
                    continue
            h,step,zero,single=requests[request_no%len(requests)];request_no+=1
            patterns.solve(pool,f'R{request_no:04d}',h,step,14,zero,single)
    except TimeoutError as exc:print('BUDGET_STOP',str(exc),flush=True)
    finally:
        write(root/'worker_end.json',dict(cpu_s=time.process_time(),wall_s=time.monotonic()-startwall,checkpoints=len(records),method=args.method,seed=args.seed))
if __name__=='__main__':main()
