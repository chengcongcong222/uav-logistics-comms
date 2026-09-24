"""XB1 Q3 uses the independent E8 full-flight validator at Gamma=0.

Only the input trajectory registry is extended. No solver feasibility routine
is imported; all route/energy/radio/calendar calculations remain independent.
"""
import argparse,json,sys,time
from pathlib import Path
import pandas as pd
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'validation/mathematical'))
import e8_validate as audit
from e52_validate_candidates import IndependentAudit,require

class ExternalAudit(IndependentAudit):
    def __init__(self):
        super().__init__()
        for pid in ['XB01','XB02']:
            frame=pd.read_csv(ROOT/f'results/q2/pareto_schedules/{pid}/transport_trace.csv',float_precision='round_trip')
            for sid,rows in frame.groupby('task_id'):
                require(not (rows.groupby('time')[['x','y','z']].nunique()>1).any().any(),'Conflicting XB trajectory')
                rows=rows.sort_values('time').drop_duplicates('time')
                self.traces[pid,sid]=(rows.time.to_numpy(float),rows[['x','y','z']].to_numpy(float))

def run(pid,step=.5,representative=False):
    paths=sorted((ROOT/'results/xb1/q3'/pid/'solutions').iterdir());results=[]
    if representative:
        paths=[min(paths,key=lambda p:tuple(json.loads((p/f'joint_metrics_{pid}.json').read_text())[k] for k in ['J_late','J_norm','joint_makespan_s']))]
    audit.IndependentAudit=ExternalAudit
    for p in paths:
        print('AUDIT_START',p.name,step,flush=True);audit.OUT=p
        try:
            result=audit.validate_plan(pid,step);result['status']='XB1_Q3_INDEPENDENTLY_VALIDATED';result['solution_id']=p.name
        except Exception as exc:
            result=dict(status='XB1_Q3_VALIDATION_FAILED',solution_id=p.name,error=str(exc))
            (p/f'validation_{step}.json').write_text(json.dumps(result,indent=2)+'\n');raise
        (p/f'validation_{step}.json').write_text(json.dumps(result,indent=2)+'\n');results.append(result)
        print('AUDIT_PASS',p.name,step,result['full_flight_samples'],flush=True)
    target=ROOT/'results/xb1/q3'/pid/f'validation_{step}.json'
    target.write_text(json.dumps(dict(status='XB1_Q3_INDEPENDENTLY_VALIDATED',solutions=results),indent=2)+'\n')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('pid');p.add_argument('--step',type=float,default=.5);p.add_argument('--representative',action='store_true');a=p.parse_args();run(a.pid,a.step,a.representative)
