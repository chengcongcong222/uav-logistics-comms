"""Active dominance challenges with explicit domain and inclusion limitations."""
import json,math,time
import numpy as np
from src.reset.geometry import OUT,write
from src.reset.patterns import solve
from src.reset.q3 import configure,ResetEngine,export_new
from src.q3.e7_core import Timing
from src.q3.e7_pareto import dominates

def q2():
    pool=json.loads((OUT/'pattern_pool.json').read_text());records=[]
    for i,pid in enumerate(['A03','A11','A12','B01','B02'],1):
        m=json.loads((OUT/'q2/pareto_schedules'/pid/'metadata.json').read_text());new=f'C{i:02d}'
        ans=solve(pool,new,horizon=math.floor(m['makespan']),step=180,limit=20,zero=True,challenge=m)
        r=dict(source=pid,challenger=new,result=ans,domain='own generated 2903-pattern pool; 180 s outward resource grid; all four Q2 criteria bounded; J_late=0 equality branch',primary_reduction_branch='impossible because certified incumbent J_late=0 and tardiness nonnegative',continuous_incumbent_not_guaranteed_in_domain=True,certificate='NO_RESTRICTED_OR_GLOBAL_NONDOMINANCE_PROOF')
        if ans:
            def convert(z):return dict(J_late=z['J_late'],J_norm=z['J_norm'],joint_makespan_s=z['makespan'],total_energy_kwh=z['energy'],transport_sorties=z['sorties'],relay_sorties=0)
            r['dominates']=dominates(convert(ans),convert(m))
        records.append(r);write(OUT/'q2_dominance_challenges.json',records)

def q3():
    configure();records=[]
    for pid in ['A03','A11','B01','B02','AN01']:
        paths=sorted((OUT/'q3'/pid/'solutions').glob('*/witness.json'))
        if not paths:continue
        e=ResetEngine(pid)
        for path in paths:
            seed=json.loads(path.read_text());m=seed['metrics'];attempts=[];winner=None
            branches=['equal_lateness']+(['strictly_lower_lateness'] if m['J_late']>1e-4 else [])
            for branch in branches:
                for objective in ['timeliness','makespan','energy']:
                    model=Timing(e,pid,seed['groups'],objective=objective,late_budget=max(0,m['J_late']-(1e-3 if branch=='strictly_lower_lateness' else 0)))
                    model.bounds[model.makespan]=(0,m['joint_makespan_s'])
                    if branch=='equal_lateness':
                        row={j:float(v) for j,v in enumerate(model.norm_c) if v};constant=float(np.sum(model.weights*model.original_delivery/model.deadlines)/sum(model.weights))
                        model.rows.append(row);model.upper.append(m['J_norm']-constant+1e-10)
                    # Sufficient conservative energy cap. Idle-hover is charged
                    # at active power here, so incumbent inclusion must be tested.
                    energy={}
                    for j in range(model.k):energy[model.n+2*j]=-1.1/3600;energy[model.n+2*j+1]=1.1/3600
                    model.rows.append(energy);model.upper.append(m['total_energy_kwh']-m['transport_energy_kwh']-model.energy_constant+1e-8)
                    x=np.zeros(model.dim)
                    for sid,v in seed['shifts'].items():x[model.idx[sid]]=v
                    for j,r in enumerate(seed['selected']):x[model.n+2*j]=r['service_start_s'];x[model.n+2*j+1]=r['service_end_s']
                    actual=model.original_delivery+np.array([seed['shifts'][sid] for sid in model.delivery.sortie_id]);x[model.late_offset:model.makespan]=np.maximum(0,actual-model.deadlines);x[model.makespan]=m['joint_makespan_s']
                    inclusion=all(sum(x[j]*v for j,v in row.items())<=cap+1e-6 for row,cap in zip(model.rows,model.upper))
                    tick=time.monotonic();ans=model.solve(seed['sequences'],node_limit=5);improved=ans is not None and dominates(ans['metrics'],m)
                    attempts.append(dict(branch=branch,objective=objective,incumbent_satisfies_linear_domain=inclusion,wall_s=time.monotonic()-tick,lp_solves=model.lp_solves,found_feasible=ans is not None,dominates=improved,node_limit=5))
                    if improved:winner=ans;break
                if winner:break
            r=dict(source=path.parent.name,domain='fixed transport structure and relay grouping/sites/sequences; free transport resource allocation and clocks; conservative energy inequality',attempts=attempts,proof='NONE: bounded resource repair and possibly excluded incumbent; absence of a challenger is not a nondominance certificate')
            if winner:
                ident=path.parent.name+'_CH';export_new(e,winner,ident);r['challenger']=ident;r['status']='DOMINATING_CANDIDATE_REQUIRES_INDEPENDENT_VALIDATION'
            else:r['status']='NO_DOMINATOR_FOUND_IN_DECLARED_CHALLENGE'
            records.append(r);write(OUT/'q3_dominance_challenges.json',records);print('CHALLENGE',r['source'],r['status'],flush=True)

if __name__=='__main__':
    import sys
    q2() if sys.argv[1]=='q2' else q3()
