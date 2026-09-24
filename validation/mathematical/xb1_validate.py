"""XB1 independent arithmetic, source identity, calendar and trace audit.

Imports existing independent E7 transport audit, not the Q2 evaluator/scheduler.
"""
import hashlib,json,sys,shutil
from pathlib import Path
import pandas as pd
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'validation/mathematical'))
import e7_validate as independent
OUT=ROOT/'results/xb1'
def check_package(path,pid,geometry=None):
    frame=pd.read_csv(path/'q2_sorties.csv'); delivery=pd.read_csv(path/'q2_box_delivery.csv')
    for target,source in [('transport_sorties','q2_sorties'),('box_delivery','q2_box_delivery'),('transport_uav_calendar','q2_uav_calendar'),('transport_battery_calendar','q2_battery_calendar')]:
        shutil.copyfile(path/(source+'.csv'),path/(target+'_'+pid+'.csv'))
    old=independent.OUT;oldread=independent.read;oldq3=independent.Q3
    try:
        independent.OUT=path
        independent.Q3=path.parents[2]/'q3'
        if geometry is not None:
            independent.read=lambda p:geometry.copy() if Path(p).name=='route_geometry.csv' else oldread(p)
        metrics,_=independent.validate_transport(pid,{s:0. for s in frame.sortie_id})
    finally:independent.OUT=old;independent.read=oldread;independent.Q3=oldq3
    # Verify every trace waypoint against a separately reconstructed flight.
    trace=pd.read_csv(path/'transport_trace.csv');nodes=pd.read_csv(ROOT/'data/processed/nodes.csv').set_index('node_id');types=pd.read_csv(ROOT/'data/processed/transport_uav_types.csv').set_index('uav_type')
    geom=(geometry if geometry is not None else pd.read_csv(ROOT/'data/processed/route_geometry.csv')).set_index(['from_id','to_id'])
    count=0
    for r in frame.itertuples():
        typ=types.loc[r.uav_type];seq=['O01']+r.service_sequence.split('>')+['O01'];expected=[]
        def position(n,z=None):
            row=nodes.loc[n];return [row.x_m,row.y_m,z if z is not None else row.ground_elevation_m+(0 if n=='O01' else 30)]
        def add(t,n,mode,role,z=None):expected.append((t,*position(n,z),mode,role))
        add(r.preparation_start_s,'O01','prep','start');add(r.takeoff_s,'O01','prep','end');add(r.takeoff_s,'O01','takeoff','instant');t=r.takeoff_s
        for a,b in zip(seq[:-1],seq[1:]):
            g=geom.loc[a,b];z=g.planned_cruise_altitude_m
            add(t,a,'climb','start');t+=g.climb_height_m/typ.max_climb_mps;add(t,a,'climb','end',z)
            add(t,a,'cruise','start',z);t+=g.horizontal_distance_m/typ.cruise_speed_mps;add(t,b,'cruise','end',z)
            add(t,b,'descent','start',z);t+=g.descent_height_m/typ.max_descend_mps;add(t,b,'descent','end')
            if b=='O01':add(t,b,'return','instant')
            else:
                add(t,b,'handover_start','start');t+=typ.handover_base_s+len(delivery[(delivery.sortie_id==r.sortie_id)&(delivery.service_id==b)])*typ.handover_per_box_s;add(t,b,'handover_end','end')
        actual=trace[trace.task_id==r.sortie_id];assert len(actual)==len(expected)
        for t,x,y,z,mode,role in expected:
            matched=actual[(actual['mode']==mode)&(actual.phase_role==role)&((actual.time-t).abs()<1e-5)]
            assert any(abs(v.x-x)<1e-5 and abs(v.y-y)<1e-5 and abs(v.z-z)<1e-5 and v.node_id==r.uav_id for v in matched.itertuples()),(r.sortie_id,t,mode)
            count+=1
    metrics.update(status='XB1_Q2_INDEPENDENTLY_VALIDATED',trace_waypoints_checked=count,checks=['80 boxes exactly once','mass and volume','per-leg payload and energy','31 hard deadlines','typed UAV non-overlap','typed battery SOC and recharge non-overlap','J_late/J_norm recomputed','every trajectory waypoint reconstructed'])
    meta=json.loads((path/'metadata.json').read_text())
    for a,b in [('J_late','J_late'),('J_norm','J_norm'),('energy','transport_energy_kwh'),('makespan','transport_makespan_s')]:independent.close(meta[a],metrics[b],a)
    metrics['artifact_sha256']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in path.glob('*') if p.is_file() and not p.name.startswith('validation')}
    (path/'validation.json').write_text(json.dumps(metrics,indent=2)+'\n')
    return metrics

def main():
    results=[]
    for name,pid in [('run01','XB01'),('run02','XB02')]:
        p=ROOT/'results/q2/pareto_schedules'/pid
        source=json.loads((OUT/(name+'_structure.json')).read_text())
        flights=pd.read_csv(p/'q2_sorties.csv');delivery=pd.read_csv(p/'q2_box_delivery.csv')
        for i,s in enumerate(source,1):
            sid=f'M{i:03d}';r=flights[flights.sortie_id==sid].iloc[0]
            assert r.uav_type==s['uav_type'] and r.service_sequence.split('>')==s['service_sequence']
            for node,bs in s['boxes_by_service'].items():assert set(delivery[(delivery.sortie_id==sid)&(delivery.service_id==node)].box_id)==set(bs)
        result=check_package(p,pid);result.update(pareto_id=pid,source_structure_verified=True);results.append(result);print(pid,result['J_late'],result['transport_energy_kwh'],result['transport_makespan_s'],flush=True)
    (OUT/'validation.json').write_text(json.dumps(dict(gate='XB1_Q2_EXTERNAL_STRUCTURES_VERIFIED',solutions=results),indent=2)+'\n')
if __name__=='__main__':main()
