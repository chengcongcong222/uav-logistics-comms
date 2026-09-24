"""Audit user-supplied GPT witnesses at their original clocks, before reoptimization."""
import json,sys
import pandas as pd
from src.reset.geometry import ROOT,OUT,write
from src.xb1.audit import export
from src.q2.solve_q2 import load_tables
from src.q2.evaluator import MissionEvaluator
sys.path.insert(0,str(ROOT/'validation/mathematical'))
from xb1_validate import check_package

def main():
    t=load_tables();ev=MissionEvaluator(t);results=[]
    for tag in ['R_FAST','R_BALANCED','R_ENERGY']:
        source=OUT/'source/solutions'/tag;p=next(source.glob('*_polished_schedule.json'));raw=json.loads(p.read_text());missions=[]
        for i,r in enumerate(raw,1):
            m=ev.evaluate_mission(r['type'],{r['service']:r['boxes']},[r['service']]);assert m is not None
            for field,target in [('energy','energy_kwh'),('duration','relative_return_time'),('prep','relative_takeoff_time')]:assert abs(r[field]-getattr(m,target))<1e-5,(tag,i,field,r[field],getattr(m,target))
            m.mission_id=f'M{i:03d}';m.preparation_start_s=r['start'];m.takeoff_s=r['start']+m.relative_takeoff_time;m.return_s=r['start']+m.relative_return_time;m.delivery_times_s={s:r['start']+v for s,v in m.relative_delivery_times.items()}
            index=int(r['uav_id'].split('U')[1])-1;m.uav_id=list(t['uavs'][t['uavs'].uav_type==m.uav_type].uav_id)[index]
            m.battery_id=f"BAT-{m.uav_type}-{int(r['battery_id'].rsplit('B',1)[1]):02d}";missions.append(m)
        dest=OUT/'supplied_audit/q2/pareto_schedules'/tag;export(missions,t,dest,tag);audit=check_package(dest,tag);audit['given_clocks_preserved']=True;audit['source_file']=str(p.relative_to(ROOT));results.append(dict(name=tag,**audit));print(tag,audit['J_late'],audit['transport_makespan_s'],audit['transport_energy_kwh'],flush=True)
    write(OUT/'supplied_witness_audit.json',dict(status='THREE_SUPPLIED_Q2_WITNESSES_CROSS_VALIDATED',solutions=results))
if __name__=='__main__':main()
