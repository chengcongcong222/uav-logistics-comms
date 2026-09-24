"""Replay validated Pareto witnesses and map epsilon budgets to executions."""
import argparse,copy,hashlib,subprocess,sys,tempfile
from src.q3.e7_export import *


def replay(solution_id,destination,validate=True):
    src=OUT/'solutions'/solution_id
    witness=json.loads((src/'witness.json').read_text());e=engine_for(witness['pareto_id'])
    for f,h in json.loads((OUT/'input_manifest.json').read_text())['hashes'].items():
        assert hashlib.sha256((ROOT/f).read_bytes()).hexdigest()==h,f
    rebuilt=[]
    for old in witness['selected']:
        r=sortie_column(e,witness['pareto_id'],old['site_id'],old['task_ids'],witness['shifts'])
        assert r is not None
        for k in ['preparation_start_s','takeoff_s','service_start_s','service_end_s','return_s','energy_ready_s','total_energy_kwh']:
            assert abs(r[k]-old[k])<1e-6,k
        r.update(relay_id=old['relay_id'],energy_component_id=old['energy_component_id']);rebuilt.append(r)
    witness['selected']=rebuilt;dest=export_solution(e,witness,solution_id,destination)
    if validate:
        subprocess.run([sys.executable,str(ROOT/'validation/mathematical/e7_validate.py'),'--directory',str(dest),'--plan',witness['pareto_id']],check=True)
    return dest


def check_all():
    records=[];temporary=OUT/'replay_tmp';temporary.mkdir(exist_ok=True)
    table=read(OUT/'provisional_pareto.csv')
    for sid in table.solution_id:
        src=OUT/'solutions'/sid
        with tempfile.TemporaryDirectory(dir=temporary) as tmp:
            dest=replay(sid,tmp,validate=False);compared=[]
            for p in src.glob('*.csv'):
                if p.name.startswith(('independent_','communication_violations_')):continue
                q=dest/p.name
                # CSV encodes identical execution values; no solver is called.
                assert q.read_bytes()==p.read_bytes(),(sid,p.name)
                compared.append(p.name)
            records.append(dict(solution_id=sid,status='EXECUTION_REPLAY_BYTE_IDENTICAL',compared_csv=compared))
    write_json(OUT/'replay_checks.json',dict(status='ALL_FINAL_WITNESSES_REPLAYED',solutions=records))


def choose(epsilon,objective):
    assert epsilon>=0
    catalog=json.loads((OUT/'budget_catalog.json').read_text());anchor=catalog['best_known_TimelinessKey']
    table=read(OUT/'pareto_solutions.csv');eligible=[]
    for r in table.to_dict('records'):
        metric='J_late' if anchor[0]>1e-8 else 'J_norm';limit=(1+epsilon)*(anchor[0] if metric=='J_late' else anchor[1])
        if r[metric]<=limit+1e-4 and (anchor[0]>1e-8 or r['J_late']<=1e-8):eligible.append(r)
    assert eligible,'No validated witness within requested epsilon budget'
    winner=min(eligible,key=lambda m:(objective_key(dict(metrics=m),objective),m['solution_id']))
    return winner['solution_id'],metric,limit


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--check-all',action='store_true');p.add_argument('--solution')
    p.add_argument('--epsilon',type=float);p.add_argument('--objective',choices=['makespan','energy','relay_sorties','timeliness'],default='makespan')
    p.add_argument('--output');a=p.parse_args()
    if a.check_all:check_all()
    else:
        sid=a.solution
        if a.epsilon is not None:
            sid,metric,budget=choose(a.epsilon,a.objective);print('BUDGET_SELECTION',sid,metric,budget,flush=True)
        assert sid and a.output,'Provide a solution or epsilon, and an output directory'
        replay(sid,a.output,validate=True)
