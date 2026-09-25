"""One isolated archive-generation run, never a formal experiment in P1.1."""
import argparse,json,math,os,random,resource,sys,time,warnings
from pathlib import Path
from src.bench_p1.common import OUT,DEV_SEEDS,METHODS,Preference,write,digest,append
def main():
    p=argparse.ArgumentParser();p.add_argument('scope',choices=METHODS);p.add_argument('method');p.add_argument('seed',type=int);p.add_argument('--budget',type=float,required=True);p.add_argument('--core',type=int,required=True);p.add_argument('--root',required=True);a=p.parse_args()
    assert a.seed in DEV_SEEDS and a.method in METHODS[a.scope]
    os.sched_setaffinity(0,{a.core});resource.setrlimit(resource.RLIMIT_CPU,(math.ceil(2*a.budget)+1,math.ceil(2*a.budget)+2))
    root=Path(a.root).resolve();root.mkdir(parents=True,exist_ok=True);records=[];serial=0;phase='imports'
    # Solver workers are in-process HiGHS; reject child processes rather than
    # quietly allowing unbilled descendant CPU. Also log all input opens.
    reads=set()
    def hook(event,args):
        if event in ['subprocess.Popen','os.system','os.fork','os.posix_spawn']:raise RuntimeError('Unbilled child processes prohibited')
        if event=='open' and isinstance(args[0],(str,bytes)):
            path=os.fsdecode(args[0]);reads.add(path)
            if 'evaluation_only_' in path or path.endswith('/p1_setup/preferences.json'):raise RuntimeError('Evaluation preferences unavailable to solver')
    sys.addaudithook(hook)
    def remaining():return a.budget-time.process_time()
    def stage(name):
        nonlocal phase
        phase=name;write(root/'phase.json',dict(phase=name,cpu_s=time.process_time()))
    write(root/'config.json',dict(scope=a.scope,method=a.method,seed=a.seed,cpu_cap_s=a.budget,core=a.core,threads=1,formal=False,calibration_scale_status='BOOTSTRAP_PHYSICAL_SCALES_NOT_FROZEN_FORMAL',scope_cost='imports+fresh B0+pool+private templates+models+search+export',subprocess_policy='DENY',search_manifest_sha256=digest(OUT/'inputs'/f'search_{a.scope}.json')))
    try:
        import numpy as np
        from scipy.optimize import milp,linprog
        from src.reset.geometry import tables
        from src.q2.evaluator import MissionEvaluator
        from src.q2.scheduler import ResourceDecoder
        from src.q2.initial_solution import build_b0
        from src.xb1.audit import export
        from src.bench_p1 import patterns
        from src.bench_p1.challenge import challenge
        from src.bench_p1.alns import search
        warnings.filterwarnings('ignore',message='Unrecognized options detected')
        def solver(fn,*args,**kwargs):
            if remaining()<1:raise TimeoutError('before solver')
            opts=dict(kwargs.get('options',{}));opts.update(threads=1,random_seed=a.seed,time_limit=max(.01,min(opts.get('time_limit',8),8,remaining()*.8)))
            kwargs['options']=opts;return fn(*args,**kwargs)
        limited=lambda *args,**kwargs:solver(milp,*args,**kwargs)
        limited_lp=lambda *args,**kwargs:solver(linprog,*args,**kwargs)
        tab=tables();ev=MissionEvaluator(tab);dec=ResourceDecoder(tab);rng=random.Random(a.seed)
        pref=Preference(a.scope,root)
        def save(decoded,origin):
            nonlocal serial
            if remaining()<.5:raise TimeoutError('before export')
            serial+=1;pid=f'P{serial:04d}';tmp=root/'partial'/pid;dest=root/'q2/pareto_schedules'/pid
            metrics=export(decoded,tab,tmp,pid)
            if remaining()<.05:raise TimeoutError('export exceeded budget')
            dest.parent.mkdir(parents=True,exist_ok=True);os.replace(tmp,dest)
            row=dict(pid=pid,scope='Q2',origin=origin,preference_id=pref.ident,cpu_ready_s=time.process_time(),metrics=metrics,mission_file=str(dest/'missions.json'),package=str(dest))
            records.append(row);write(root/'checkpoints.json',records);return metrics
        stage('common_initialization');base=build_b0(ev,dec);save(base.decoded,'COMMON_FRESH_B0')
        if a.scope=='Q2' and a.method in ['UNIFORM_LNS','ALNS']:
            stage('neighborhood_search');search(base,rng,ev,dec,pref,remaining,save,adaptive=a.method=='ALNS');return
        patterns.OUT=root;patterns.milp=limited
        patterns.export=lambda decoded,t,dest,tag:save(decoded,'PREFERENCE_PATTERN_MILP')
        stage('pattern_pool');pool=patterns.build_pool();rng.shuffle(pool['patterns'])
        write(root/'pool_signature.json',dict(classes=pool['classes'],patterns=pool['patterns']))
        if a.scope=='Q3':
            from src.bench_p1.q3_adapter import run
            stage('q3_pipeline');run(a.method,root,pool,base,tab,pref,patterns,remaining,limited,limited_lp,records,stage);return
        challenged=set();request=0
        while remaining()>1:
            if a.method=='POOL_CHALLENGE' and time.process_time()>.55*a.budget:
                options=[r for r in records if r['pid'] not in challenged]
                if options:
                    target=min(options,key=lambda r:pref.key(r['metrics'],'challenge_selection'));challenged.add(target['pid'])
                    stage('active_challenge');answer,info=challenge(target,tab,limited,rng,pref);append(root/'challenge_attempts.jsonl',dict(preference_id=pref.ident,source=target['pid'],**info))
                    if answer is not None:save(answer,'PREFERENCE_CHALLENGE')
                    pref.next();continue
            stage('pattern_scheduling');request+=1
            patterns.solve(pool,f'R{request:04d}',horizon=12000,step=180,limit=8,zero=True,single=False,preference=pref)
            pref.next()
    except TimeoutError as exc:write(root/'budget_stop.json',dict(reason=str(exc),phase=phase))
    except Exception as exc:
        write(root/'error.json',dict(type=type(exc).__name__,error=str(exc),phase=phase));raise
    finally:
        write(root/'input_access.json',sorted(reads))
        write(root/'worker_end.json',dict(cpu_s=time.process_time(),phase=phase,checkpoints=len(records),children_cpu_s=resource.getrusage(resource.RUSAGE_CHILDREN).ru_utime+resource.getrusage(resource.RUSAGE_CHILDREN).ru_stime))
if __name__=='__main__':main()
