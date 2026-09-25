"""Development-only POSIX CPU supervision on distinct physical cores."""
import argparse,json,os,signal,subprocess,sys,time,shutil
from pathlib import Path
from src.bench.run import cpu
from src.bench_p1.common import ROOT,OUT,DEV_SEEDS,METHODS,write,digest
def physical_cores():
    found={}
    for block in Path('/proc/cpuinfo').read_text().strip().split('\n\n'):
        d={k.strip():v.strip() for k,v in (l.split(':',1) for l in block.splitlines() if ':' in l)}
        i=int(d['processor'])
        if i in os.sched_getaffinity(0):found.setdefault((d['physical id'],d['core id']),i)
    return list(found.values())
def main():
    p=argparse.ArgumentParser();p.add_argument('scope',choices=METHODS);p.add_argument('--budget',type=int,choices=[30,120,300],required=True);p.add_argument('--revision',default='v1');a=p.parse_args()
    dest=OUT/'runs'/f'{a.scope}_{a.budget}_{a.revision}';assert not dest.exists(),'never overwrite a development run'
    dest.mkdir(parents=True);cores=physical_cores();assert len(cores)>=len(METHODS[a.scope])
    write(dest/'protocol.json',dict(scope=a.scope,budget=a.budget,methods=METHODS[a.scope],seeds=DEV_SEEDS,physical_cores=cores,source_sha256={str(p.relative_to(ROOT)):digest(p) for p in (ROOT/'src/bench_p1').glob('*.py')},cpu_clock='POSIX process CPU',maximum_overshoot_s=.2,formal=False))
    for p in (ROOT/'src/bench_p1').glob('*.py'):
        target=dest/'source_snapshot'/p.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,target)
    env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',NUMEXPR_NUM_THREADS='1',PYTHONHASHSEED='0');results=[]
    for si,seed in enumerate(DEV_SEEDS):
        active=[]
        for mi,method in enumerate(METHODS[a.scope]):
            root=dest/f'{method}_{seed}';root.mkdir();log=(root/'worker.log').open('w');core=cores[(mi+si)%len(cores)]
            proc=subprocess.Popen([sys.executable,'-u','-m','src.bench_p1.worker',a.scope,method,str(seed),'--budget',str(a.budget),'--core',str(core),'--root',str(root)],cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            active.append(dict(proc=proc,root=root,log=log,start=time.monotonic(),lastcpu=0.,kill=None,core=core,method=method,maxthreads=0,children=set()))
        while active:
            for t in list(active):
                proc=t['proc'];used=cpu(proc.pid)
                if used is not None:t['lastcpu']=max(t['lastcpu'],used)
                try:
                    status=Path(f'/proc/{proc.pid}/status').read_text()
                    t['maxthreads']=max(t['maxthreads'],int(next(l.split()[1] for l in status.splitlines() if l.startswith('Threads:'))))
                    t['children'].update(Path(f'/proc/{proc.pid}/task/{proc.pid}/children').read_text().split())
                except (FileNotFoundError,ProcessLookupError,StopIteration):pass
                if proc.poll() is None:
                    if t['lastcpu']>=a.budget:t['kill']='CPU_BUDGET';os.killpg(proc.pid,signal.SIGKILL)
                    elif time.monotonic()-t['start']>max(180,4*a.budget):t['kill']='WALL_WATCHDOG';os.killpg(proc.pid,signal.SIGKILL)
                    continue
                t['log'].close();root=t['root'];f=root/'checkpoints.json';rows=json.loads(f.read_text()) if f.exists() else []
                end=root/'worker_end.json'
                total=max(t['lastcpu'],json.loads(end.read_text())['cpu_s'] if end.exists() else 0)
                r=dict(method=t['method'],seed=seed,scope=a.scope,cpu_cap_s=a.budget,observed_cpu_s=total,wall_s=time.monotonic()-t['start'],core=t['core'],exit_code=proc.returncode,termination=t['kill'] or 'WORKER_FINISHED',accepted=[x['pid'] for x in rows if x['cpu_ready_s']<=a.budget],root=str(root.relative_to(ROOT)),maximum_observed_threads=t['maxthreads'],observed_children=sorted(t['children']))
                write(root/'supervisor.json',r);results.append(r);write(dest/'run_status.json',results);print('RUN_DONE',r,flush=True);active.remove(t)
            time.sleep(.01)
if __name__=='__main__':main()
