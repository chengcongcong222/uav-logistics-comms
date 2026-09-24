"""Independent G2 Q3 audit: new trajectories and independently derived relay legs."""
import argparse,json,math,sys
from pathlib import Path
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'validation/mathematical'))
import e8_validate as audit
from e52_validate_candidates import IndependentAudit
from reset_geometry_validate import independent_max
OUT=ROOT/'results/reset'
class Checker(IndependentAudit):
    def __init__(self):
        super().__init__();self.geocache={}
        for p in (OUT/'q2/pareto_schedules').glob('*/transport_trace.csv'):
            frame=pd.read_csv(p,float_precision='round_trip')
            for sid,r in frame.groupby('task_id'):
                assert not (r.groupby('time')[['x','y','z']].nunique()>1).any().any()
                r=r.sort_values('time').drop_duplicates('time');self.traces[p.parent.name,sid]=(r.time.to_numpy(float),r[['x','y','z']].to_numpy(float))
    def energy(self,site,duration):
        p=self.params;key=(site.x_m,site.y_m)
        if key not in self.geocache:self.geocache[key]=independent_max(self.dem,self.origin[:2],key)
        cruise=max(self.geocache[key]+50,self.origin[2],site.z_amsl_m);a=cruise-self.origin[2];b=cruise-site.z_amsl_m;d=math.hypot(site.x_m-self.origin[0],site.y_m-self.origin[1])
        flight=2*p['cruise_power_kw']*d/p['cruise_speed_mps']/3600+p['takeoff_mass_kg']*9.80665*(a+b)/(p['climb_eff']*3.6e6)
        setup=(p['hover_power_kw']+p['comm_power_kw'])*p['setup_time_s']/3600;service=(p['hover_power_kw']+p['comm_power_kw'])*duration/3600;total=flight+setup+service
        return dict(flight_energy_kwh=flight,setup_energy_kwh=setup,service_energy_kwh=service,total_energy_kwh=total,energy_margin_kwh=(1-p['rho'])*p['energy_kwh']-total,return_soc=1-total/p['energy_kwh'],outbound_time_s=a/p['max_climb_mps']+d/p['cruise_speed_mps']+b/p['max_descend_mps'],return_time_s=b/p['max_climb_mps']+d/p['cruise_speed_mps']+a/p['max_descend_mps'])

def run(pid,step=.5):
    audit.IndependentAudit=Checker;audit.Q3=OUT/'q3';audit.DATA=OUT/'geometry';results=[]
    for p in sorted((OUT/'q3'/pid/'solutions').iterdir()):
        audit.OUT=p;print('AUDIT',p.name,step,flush=True)
        try:r=audit.validate_plan(pid,step);r.update(status='G2_Q3_INDEPENDENTLY_VALIDATED',solution_id=p.name)
        except Exception as exc:
            (p/f'validation_{step}.json').write_text(json.dumps(dict(status='G2_Q3_VALIDATION_FAILED',error=str(exc)),indent=2)+'\n');raise
        (p/f'validation_{step}.json').write_text(json.dumps(r,indent=2)+'\n');results.append(r);print('PASS',p.name,r['full_flight_samples'],flush=True)
    (OUT/'q3'/pid/f'validation_{step}.json').write_text(json.dumps(dict(status='G2_Q3_INDEPENDENTLY_VALIDATED',solutions=results),indent=2)+'\n')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('pid');p.add_argument('--step',type=float,default=.5);a=p.parse_args();run(a.pid,a.step)
