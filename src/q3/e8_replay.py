"""Budget selection and deterministic execution-CSV reconstruction."""
from pathlib import Path
import hashlib,json,shutil,tempfile
from src.q3.e8_search import *
from src.q3.e8_export import export_solution
from src.q3.e7_core import engine_for
from src.q3.e7_export import export_solution as export_zero

def check_all():
    records=[]
    with tempfile.TemporaryDirectory(prefix='e8_replay_') as tmp:
        for gamma in [0,2,4,6]:
            dest=gamma_dir(gamma)
            if not (dest/'provisional_pareto.csv').exists():continue
            engine=engine_for() if gamma==0 else load_engine(gamma)
            for sid in read(dest/'provisional_pareto.csv').solution_id:
                source=dest/'solutions'/sid;target=Path(tmp)/sid
                witness=json.loads((source/'witness.json').read_text())
                if gamma==0:export_zero(engine,witness,sid.replace('Q3E8_G00_','Q3E7_'),target)
                else:export_solution(engine,witness,sid,target)
                names=[p.name for p in source.glob('*.csv') if not p.name.startswith(('communication_violations','independent_candidate_audit'))]
                for name in names:assert (source/name).read_bytes()==(target/name).read_bytes(),(sid,name)
                records.append(dict(solution_id=sid,Gamma_C_db=gamma,csv_files=len(names),byte_identical=True))
    write_json(OUT/'replay_checks.json',records);print('REPLAY_ALL',len(records),flush=True)

def select(gamma,epsilon,objective,output):
    dest=gamma_dir(gamma)
    if not (dest/'budget_catalog.json').exists():raise ValueError('No validated executable witness at this Gamma; infeasibility is not proven')
    catalog=json.loads((dest/'budget_catalog.json').read_text())
    query=next(q for q in catalog['queries'] if abs(q['epsilon']-epsilon)<1e-12 and q['objective']==objective)
    source=dest/'solutions'/query['solution_id']
    validation=json.loads((source/'validation_P01_0.5.json').read_text())
    assert validation['status']=='E8_PLAN_INDEPENDENTLY_VALIDATED'
    for f,h in validation['artifact_sha256'].items():assert hashlib.sha256((ROOT/f).read_bytes()).hexdigest()==h
    output=Path(output);assert not output.exists(),'Output must be new; preserve prior audit artifacts'
    shutil.copytree(source,output)
    write_json(output/'selection.json',dict(Gamma_C_db=gamma,**query,source=str(source.relative_to(ROOT))))
    print(json.dumps(query,indent=2))

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--check-all',action='store_true');p.add_argument('--gamma',type=int,choices=[0,2,4,6]);p.add_argument('--epsilon',type=float,default=.02);p.add_argument('--objective',choices=['makespan','energy','relay_sorties'],default='energy');p.add_argument('--output');a=p.parse_args()
    if a.check_all:check_all()
    else:select(a.gamma,a.epsilon,a.objective,a.output)
