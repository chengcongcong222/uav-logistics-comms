"""Known-positive sequential adapter fixture, NOT a cold-start method result."""
import copy,json,sys
from pathlib import Path
import numpy as np
from src.bench_p1.common import ROOT,OUT,Preference,write
from src.bench_p1 import q3_adapter as adapter,joint_kernel
from src.reset.geometry import tables,FlightDem
from src.q2.mission import Mission
from src.xb1.audit import export
from src.q3.e6_resources import read
from src.q3.e7_core import Timing as OriginalTiming

def main():
    source=OUT/'runs/Q3_300_v3/JOINT_26092511';seed=json.loads((source/'q3/P0002/solutions/Q30001/witness.json').read_text())
    original=source/'q3/P0002/solutions/Q30001'
    assert (original/'validation_0.5.json').exists(),'independent source audit required'
    root=OUT/'fixtures/sequential_positive';root.mkdir(parents=True,exist_ok=True);pid='DEVFIX'
    ms=[Mission(**m) for m in json.loads((source/'q2/pareto_schedules/P0002/missions.json').read_text())]
    for m in ms:
        shift=seed['shifts'][m.mission_id];m.preparation_start_s+=shift;m.takeoff_s+=shift;m.return_s+=shift
        m.delivery_times_s={s:t+shift for s,t in m.delivery_times_s.items()}
        m.uav_id=seed['assignments'][m.mission_id]['uav_id'];m.battery_id=seed['assignments'][m.mission_id]['battery_id']
    export(ms,tables(),root/'q2/pareto_schedules'/pid,pid)
    e=adapter.Engine.__new__(adapter.Engine);e.pid=pid;e.root=root;e.base=root/'q2/pareto_schedules'/pid;e.dest=root/'q3'/pid;e.dest.mkdir(parents=True,exist_ok=True)
    e.pr=adapter.resources.load_relay_params();e.origin=np.array(adapter.resources.o01_pos());e.geometry=FlightDem()
    e.sites={r['site_id']:r for r in read(original/'candidate_sites_P0002.csv').to_dict('records')}
    e.atoms=read(original/'guarded_atomic_tasks.csv').set_index('atomic_task_id',drop=False)
    for field in ['service_start_s','service_end_s']:e.atoms[field]+=e.atoms.transport_sortie_id.map(seed['shifts'])
    e.atoms.pareto_id=pid
    pairs={(r['atomic_task_id'],r['site_id']):r for r in read(original/'guarded_selected_pairs_P0002.csv').to_dict('records')}
    def pair(a,s):
        row=dict(pairs[a,s]);task=e.atoms.loc[a]
        row.update(pareto_id=pid,service_start_s=float(task.service_start_s),service_end_s=float(task.service_end_s));return row
    e.check_task=pair;e.backhaul=lambda site:None
    adapter.core.RESULTS_Q2=root/'q2';adapter.shift.RESULTS_Q2=root/'q2';adapter.exporter.RESULTS_Q2=root/'q2'
    from scipy.optimize import milp,linprog
    def limited(fn,*args,**kwargs):
        opts=dict(kwargs.get('options',{}));opts.update(threads=1,random_seed=26092511,time_limit=8);kwargs['options']=opts;return fn(*args,**kwargs)
    pref=Preference('Q3',root)
    class Fixed(OriginalTiming):
        def __init__(self,engine,_pid,groups):
            super().__init__(engine,pid,groups)
            for i in range(self.n):self.bounds[i]=(0.,0.)
        def lp(self,sequences,cuts):return adapter.preference_lp(self,sequences,cuts,pref,lambda *a,**k:limited(linprog,*a,**k))
    joint_kernel.Timing=Fixed;joint_kernel.milp=lambda *a,**k:limited(milp,*a,**k)
    answer,info=joint_kernel.relay_order_milp(e,seed['groups'],limit=8,joint_resources=True,preference=pref)
    assert answer is not None,info
    assert max(abs(s) for s in answer['shifts'].values())<1e-6,'sequential flow shifted transportation'
    adapter.export_local(e,answer,'POSITIVE')
    sys.path.insert(0,str(ROOT/'validation/mathematical'))
    import reset_q3_validate as q3
    q3.OUT=root;q3.audit.IndependentAudit=q3.Checker;q3.audit.Q3=root/'q3';q3.audit.DATA=ROOT/'results/reset/geometry';q3.audit.OUT=e.dest/'solutions/POSITIVE'
    audit=q3.audit.validate_plan(pid,.5)
    write(root/'validation.json',dict(audit,fixture_status='SEQUENTIAL_POSITIVE_CONTROL_INDEPENDENTLY_VERIFIED',not_a_cold_start_benchmark=True,source='fresh development JOINT witness; shifted transport is fixture input, never fed back to comparison runs',solver_info=info))
    print('SEQUENTIAL_POSITIVE_CONTROL_INDEPENDENTLY_VERIFIED',flush=True)
if __name__=='__main__':main()
