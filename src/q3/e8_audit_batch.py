"""Run standalone independent audits; no scheduler feasibility flags accepted."""
from pathlib import Path
import concurrent.futures,json,os,subprocess,sys
ROOT=Path(__file__).resolve().parents[2]

def audit(directory,step):
    target=directory/f'validation_P01_{step}.json'
    log=directory/f'validation_{step}.log'
    with log.open('w') as stream:
        p=subprocess.run([sys.executable,str(ROOT/'validation/mathematical/e8_validate.py'),'--directory',str(directory),'--step',str(step)],
            cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT,env={**os.environ,'OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1'})
    result=json.loads(target.read_text()) if target.exists() else dict(status='MISSING_AUDIT')
    print(directory.name,step,p.returncode,result.get('status'),result.get('error'),flush=True)
    return dict(solution_id=directory.name,step=step,exit_code=p.returncode,**result)

def run(gamma):
    dest=ROOT/f'results/q3/e8/gamma_{int(gamma):02d}'
    dirs=sorted(p for p in (dest/'solutions').iterdir() if p.is_dir())
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(lambda d:audit(d,.5),dirs))
    if all(r['exit_code']==0 for r in results):results.append(audit(dirs[0],.25))
    (dest/'independent_audits.json').write_text(json.dumps(results,indent=2)+'\n')
    if not all(r['exit_code']==0 for r in results):raise SystemExit(1)

if __name__=='__main__':run(float(sys.argv[1]))
