"""G2 external controls and a time-budgeted uniform LNS baseline."""
import argparse,copy,json,random,time
from src.reset.geometry import ROOT,OUT,DATA,tables,write
from src.xb1.audit import import_specs,joint_schedule,export
from src.q2.evaluator import MissionEvaluator
from src.q2.scheduler import ResourceDecoder
from src.q2.initial_solution import build_b0
from src.q2.evaluator_sol import evaluate_solution
from src.q2.operators import DESTROY,REPAIR

def external(name,pid):
    ev=MissionEvaluator(tables());missions=[]
    for i,s in enumerate(import_specs(name),1):
        m=ev.evaluate_mission(s['uav_type'],s['boxes_by_service'],s['service_sequence']);assert m;m.mission_id=f'M{i:03d}';missions.append(m)
    decoded,info=joint_schedule(missions,tables(),limit=60)
    if decoded:info['metrics']=export(decoded,tables(),OUT/'q2/pareto_schedules'/pid,pid)
    info.update(line='EXTERNAL_XB_CONTROL',source_structure=name,geometry='G2',given_clocks_used=False)
    write(OUT/'search_logs'/f'{pid}.json',info);print(pid,info,flush=True)

def lns(limit=60):
    ev=MissionEvaluator(tables());decoder=ResourceDecoder(tables());tick=time.monotonic();rng=random.Random(2026092507)
    base=build_b0(ev,decoder);best=base;current=base;iters=0;success=0
    while time.monotonic()-tick<limit:
        d=rng.choice(list(DESTROY));r=rng.choice(list(REPAIR));fn=DESTROY[d]
        ms,loose=fn(current.missions,rng,ev) if d in ['worst_timeliness_removal','related_service_removal'] else fn(current.missions,rng)
        sol=REPAIR[r](ms,loose,rng,ev,decoder);iters+=1
        if sol:
            success+=1;key=lambda x:tuple(x.metrics[k] for k in ['J_late','J_norm','makespan','energy','sorties'])
            if key(sol)<key(best):best=sol
            if key(sol)<key(current) or rng.random()<.1:current=sol
        # Preserve-order decoder is explicitly reachable; random order remains
        # a heuristic, never a proof of structural infeasibility.
        if iters%4==0:
            raw=copy.deepcopy(current.missions);rng.shuffle(raw);ordered=evaluate_solution(raw,ev,decoder,preserve_order=True)
            if ordered and key(ordered)<key(best):best=ordered
    metrics=export(best.decoded,tables(),OUT/'q2/pareto_schedules/LNS', 'LNS')
    write(OUT/'search_logs/LNS.json',dict(line='OWN_UNIFORM_LNS_BASELINE',seed=2026092507,limit_s=limit,actual_wall_s=time.monotonic()-tick,iterations=iters,feasible_repairs=success,operator_choice='uniform; not claimed adaptive',initial_metrics=base.metrics,metrics=metrics,iteration_boundary_timeout=True));print('LNS',metrics,flush=True)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('name');a=ap.parse_args()
    if a.name=='LNS':lns()
    else:external('run01' if a.name=='B01' else 'run02',a.name)
