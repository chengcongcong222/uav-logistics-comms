"""Supervise equal CPU caps; rotate methods across cores, never accept late output."""
import argparse,ctypes,hashlib,json,math,os,platform,resource,signal,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def write(p,obj):
    p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_suffix(p.suffix+'.tmp');tmp.write_text(json.dumps(obj,indent=2)+'\n');os.replace(tmp,p)
LIBC=ctypes.CDLL(None)
LIBC.clock_getcpuclockid.argtypes=[ctypes.c_int,ctypes.POINTER(ctypes.c_int)]
LIBC.clock_getcpuclockid.restype=ctypes.c_int
def cpu(pid):
    try:
        clockid=ctypes.c_int()
        if LIBC.clock_getcpuclockid(pid,ctypes.byref(clockid))!=0:return None
        return time.clock_gettime(clockid.value)
    except OSError:return None
def main():
    p=argparse.ArgumentParser();p.add_argument('--budget',type=float,default=180);p.add_argument('--seeds',nargs='+',type=int,default=[250901,250902,250903,250904,250905]);p.add_argument('--root',default='results/ablation180_v2');a=p.parse_args()
    out=ROOT/a.root;out.mkdir(parents=True,exist_ok=True);methods=['LNS','POOL','POOL_CHALLENGE'];available=sorted(os.sched_getaffinity(0));cores=[available[0],available[len(available)//3],available[2*len(available)//3]]
    config=dict(version='CPU180_FIVE_SEEDS_Q2_V2',scope='Q2_ONLY',methods=methods,seeds=a.seeds,cpu_budget_s=a.budget,cores=cores,parallel_workers=3,core_assignment='rotate by seed index',checkpoint_cpu_cutoff_s=a.budget,supervisor_cpu_clock='POSIX clock_getcpuclockid + clock_gettime, same process CPU clock as worker process_time',supervisor_poll_s=.01,maximum_observed_cpu_overshoot_tolerance_s=.2,secondary_wall_watchdog_s=900,thread_limit=1,
        included_costs=['interpreter/imports','data loading','fresh common B0 initialization','mode generation','model construction','search','execution package exports'],excluded_costs=['supervisor monitoring','independent post-run validation','summary plots'],
        common_geometry='G2_UTM49N_STRAIGHT_NATIVE_SUPERCOVER_V1',common_physics_and_objectives=True,no_imported_solution_seeds=True,
        enhanced_protocol='same pool pipeline; after 100 process CPU seconds interleave up-to-14-wall-second fixed-structure free-resource dominance MILPs on unchallenged nondominated candidates; alternate new pattern proposals when exhausted',
        base_pool_protocol='cycle 6600/120 zero single,7200/180 zero single,9600/180 zero multi,12000/180 soft multi; each solver call capped at 14 wall seconds; seeded pattern permutation and HiGHS seed',
        lns_protocol='uniform destroy/repair, 10 percent acceptance of non-improvement, explicit randomized order every fourth iteration; record every completed feasible candidate',
        success_definitions=['at least one independently verified in-budget full Q2 execution','at least one such execution with J_late <= 1e-4'],
        hypotheses='compare search quality under identical CPU cap; do not promise POOL_CHALLENGE beats POOL or infer Q3 algorithm performance',python=sys.version,platform=platform.platform(),source_hashes={str(q.relative_to(ROOT)):hashlib.sha256(q.read_bytes()).hexdigest() for q in (ROOT/'src/bench').glob('*.py')})
    topology=[]
    for block in Path('/proc/cpuinfo').read_text().strip().split('\n\n'):
        d={k.strip():v.strip() for k,v in (line.split(':',1) for line in block.splitlines() if ':' in line)}
        topology.append({k:d.get(k) for k in ['processor','model name','physical id','core id']})
    config['cpu_topology']=topology
    write(out/'protocol.json',config);results=[];env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',NUMEXPR_NUM_THREADS='1',PYTHONHASHSEED='0')
    for batch,seed in enumerate(a.seeds):
        active=[]
        for j,method in enumerate(methods):
            name=f'{method}_{seed}';dest=out/name
            assert not dest.exists(),f'Do not overwrite prior run {dest}'
            dest.mkdir();log=open(dest/'worker.log','w');core=cores[(j+batch)%len(cores)]
            cmd=[sys.executable,'-u','-m','src.bench.worker',method,str(seed),'--budget',str(a.budget),'--core',str(core),'--root',a.root]
            proc=subprocess.Popen(cmd,cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            active.append(dict(proc=proc,log=log,name=name,core=core,start=time.monotonic(),lastcpu=0.,kill_reason=None))
        while active:
            for task in list(active):
                proc=task['proc'];used=cpu(proc.pid)
                if used is not None:task['lastcpu']=max(task['lastcpu'],used)
                if proc.poll() is None:
                    if task['lastcpu']>=a.budget:task['kill_reason']='CPU_BUDGET';os.killpg(proc.pid,signal.SIGKILL)
                    elif time.monotonic()-task['start']>900:task['kill_reason']='WALL_WATCHDOG';os.killpg(proc.pid,signal.SIGKILL)
                    continue
                task['log'].close();dest=out/task['name'];ready=[]
                if (dest/'checkpoints.json').exists():ready=json.loads((dest/'checkpoints.json').read_text())
                accepted=[r for r in ready if r['cpu_ready_s']<=a.budget]
                result=dict(run=task['name'],core=task['core'],exit_code=proc.returncode,termination=task['kill_reason'] or 'WORKER_FINISHED',observed_process_cpu_s=task['lastcpu'],wall_s=time.monotonic()-task['start'],cpu_budget_s=a.budget,accepted_checkpoints=[r['pid'] for r in accepted],discarded_after_budget=[r['pid'] for r in ready if r not in accepted])
                write(dest/'supervisor.json',result);results.append(result);write(out/'run_status.json',results);active.remove(task);print('RUN_DONE',result,flush=True)
            time.sleep(.01)
    print('ALL_RUNS_COMPLETE',len(results),flush=True)
if __name__=='__main__':main()
