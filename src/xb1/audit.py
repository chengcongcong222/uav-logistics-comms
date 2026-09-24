"""XB1: attributed external structures, local physics and fresh typed scheduling."""
import copy, hashlib, json, math, time
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.optimize import milp, Bounds, LinearConstraint
from scipy.sparse import coo_matrix
from src.q2.solve_q2 import load_tables
from src.q2.evaluator import MissionEvaluator, GateStats
from src.q2.evaluator_sol import evaluate_solution, Solution
from src.q2.scheduler import ResourceDecoder
from src.common.charging import charge_time_s
from src.common.terrain import Dem
from src.q3.e6_resources import color_intervals

ROOT=Path(__file__).resolve().parents[2]; OUT=ROOT/'results/xb1'
def write(p,obj):
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n')

def exact_geometry(tables):
    """Exact grid-boundary supercover of frozen lon/lat line interpretation.

    Includes both cells touched at an exact edge/corner. Does not silently
    replace the existing 30 m sampled authority or redefine route geometry.
    """
    dem=Dem(); inv=~dem.transform; nodes=tables['nodes'].set_index('node_id')
    rows=[]
    for r in tables['geom'].to_dict('records'):
        a=nodes.loc[r['from_id']]; b=nodes.loc[r['to_id']]
        p=np.array(inv*(a.longitude,a.latitude)); q=np.array(inv*(b.longitude,b.latitude)); d=q-p
        cuts=[0.,1.]
        for axis in range(2):
            if abs(d[axis])>1e-12:
                cuts += [(v-p[axis])/d[axis] for v in range(math.ceil(min(p[axis],q[axis])),math.floor(max(p[axis],q[axis]))+1) if 0<(v-p[axis])/d[axis]<1]
        cuts=sorted(set(cuts)); cells=set()
        for u in cuts+[(a+b)/2 for a,b in zip(cuts[:-1],cuts[1:])]:
            xy=p+u*d
            options=[]
            for v in xy:
                options.append([round(v)-1,round(v)] if abs(v-round(v))<1e-8 else [math.floor(v)])
            for c in options[0]:
                for rr in options[1]:
                    assert 0<=rr<dem.arr.shape[0] and 0<=c<dem.arr.shape[1]
                    cells.add((rr,c))
        vals=[float(dem.arr[rr,c]) for rr,c in cells]
        assert all(np.isfinite(v) and v!=dem.nodata for v in vals)
        z=max(vals);old=r['max_dem_elevation_m']
        r.update(max_dem_elevation_m=z,planned_cruise_altitude_m=z+50,
                 climb_height_m=max(0,z+50-r['origin_operation_altitude_m']),
                 descent_height_m=max(0,z+50-r['destination_operation_altitude_m']))
        rows.append(dict(r,frozen_max_dem_elevation_m=old,delta_max_dem_m=z-old,crossed_cells=len(cells)))
    return pd.DataFrame(rows)

def import_specs(name):
    source=json.loads((OUT/'source'/f'{name}_rescheduled.json').read_text())
    return [dict(source_sortie_id=r['sortie_id'],uav_type=r['type_id'],service_sequence=[x[0] for x in r['stops']],boxes_by_service=dict(r['stops'])) for r in sorted(source['sorties'],key=lambda x:x['sortie_id'])]

def joint_schedule(missions,tables,limit=60):
    # Fresh continuous starts; all expected deadlines imposed to seek J_late=0.
    # A failed bounded run does not prove the structure physically infeasible.
    n=len(missions); costs=[0.]*n+[1.]; bounds=[(0,20000)]*n+[(0,20000)]; integer=[0]*(n+1)
    rows=[]; lo=[]; hi=[]; M=50000.
    def add(row,l=-np.inf,h=np.inf): rows.append(row);lo.append(l);hi.append(h)
    def var():
        j=len(costs);costs.append(0.);bounds.append((0,1));integer.append(1);return j
    boxes=tables['boxes'].set_index('box_id'); full=tables['batteries'].set_index('uav_type')
    for i,m in enumerate(missions):
        add({i:1,n:-1},h=-m.relative_return_time)
        cap=20000
        for s,bs in m.boxes_by_service.items():
            for b in bs:
                r=boxes.loc[b]
                if pd.notna(r.expected_deadline_s):cap=min(cap,float(r.expected_deadline_s)-m.relative_delivery_times[s])
        if m.hard_deadline_latest_start is not None:cap=min(cap,m.hard_deadline_latest_start)
        bounds[i]=(0,cap)
    for kind in ['UAV','BATTERY']:
        for typ in sorted({m.uav_type for m in missions}):
            ids=[i for i,m in enumerate(missions) if m.uav_type==typ]
            count=len(tables['uavs'][tables['uavs'].uav_type==typ]) if kind=='UAV' else int(full.loc[typ].battery_pool_count)
            if len(ids)<=count:continue
            assign={i:[var() for _ in range(count)] for i in ids}
            for i in ids:add({v:1 for v in assign[i]},1,1)
            bounds[assign[ids[0]][0]]=(1,1)
            def interval(i):
                m=missions[i]
                return (0,m.relative_return_time) if kind=='UAV' else (m.relative_takeoff_time,m.relative_return_time+charge_time_s(1-m.energy_kwh/tables['types'].loc[typ].battery_energy_kwh,full.loc[typ].full_charge_time_s))
            for ii,i in enumerate(ids):
                a,b=interval(i)
                for j in ids[ii+1:]:
                    c,d=interval(j);z=var()
                    for r in range(count):
                        add({i:1,j:-1,z:M,assign[i][r]:M,assign[j][r]:M},h=3*M-b+c-1e-5)
                        add({j:1,i:-1,z:-M,assign[i][r]:M,assign[j][r]:M},h=2*M-d+a-1e-5)
    rr=[];cc=[];vv=[]
    for i,row in enumerate(rows):
        for j,v in row.items():rr.append(i);cc.append(j);vv.append(v)
    mat=coo_matrix((vv,(rr,cc)),shape=(len(rows),len(costs))).tocsc(); tick=time.monotonic()
    result=milp(np.array(costs),integrality=np.array(integer),bounds=Bounds(*np.array(bounds).T),constraints=LinearConstraint(mat,lo,hi),options={'time_limit':limit,'mip_rel_gap':.005})
    info=dict(status=int(result.status),message=result.message,runtime_s=time.monotonic()-tick,limit_s=limit,zero_lateness_constraint=True,scope='FIXED_EXTERNAL_STRUCTURE_FRESH_RESOURCE_ASSIGNMENT',variables=len(costs),objective=None if result.fun is None else float(result.fun),global_optimum_proven=False)
    if result.x is None:return None,info
    out=copy.deepcopy(missions)
    for i,m in enumerate(out):
        s=max(0,float(result.x[i]));m.preparation_start_s=s;m.takeoff_s=s+m.relative_takeoff_time;m.return_s=s+m.relative_return_time
        m.delivery_times_s={b:s+t for b,t in m.relative_delivery_times.items()}
    for typ in sorted({m.uav_type for m in out}):
        mm=[m for m in out if m.uav_type==typ]
        for kind in ['UAV','BATTERY']:
            rows=[]
            for i,m in enumerate(mm):
                end=m.return_s+(charge_time_s(1-m.energy_kwh/tables['types'].loc[typ].battery_energy_kwh,full.loc[typ].full_charge_time_s) if kind=='BATTERY' else 0)
                rows.append(dict(i=i,start=m.preparation_start_s if kind=='UAV' else m.takeoff_s,end=end))
            pool=list(tables['uavs'][tables['uavs'].uav_type==typ].uav_id) if kind=='UAV' else [f'BAT-{typ}-{i:02d}' for i in range(1,int(full.loc[typ].battery_pool_count)+1)]
            color_intervals(rows,'start','end',pool,'resource')
            for r in rows:setattr(mm[r['i']],'uav_id' if kind=='UAV' else 'battery_id',r['resource'])
    return out,info

def export(decoded,tables,dest,tag):
    import src.q2.solve_q2 as exporter
    import src.q2.export_trace as tracer
    box=tables['boxes'].set_index('box_id'); late=norm=den=0.
    for m in decoded:
        for s,bs in m.boxes_by_service.items():
            for b in bs:
                r=box.loc[b];w=float(r.priority_weight);d=float(r.expected_deadline_s);v=m.delivery_times_s[s]
                late+=w*max(0,v-d);norm+=w*v/d;den+=w
    metrics=dict(J_late=late,J_norm=norm/den,makespan=max(m.return_s for m in decoded),energy=sum(m.energy_kwh for m in decoded),sorties=len(decoded),source=tag,global_optimum_proven=False)
    dest.mkdir(parents=True,exist_ok=True);old=exporter.RESULTS_Q2
    try:
        exporter.RESULTS_Q2=dest;exporter.dump_solution(Solution(decoded=decoded,metrics=metrics),tag,MissionEvaluator(tables))
        for p in list(dest.glob('*_'+tag+'.csv')):p.rename(dest/(p.name.removesuffix('_'+tag+'.csv')+'.csv'))
    finally:exporter.RESULTS_Q2=old
    battery=tables['batteries'].set_index('uav_type');bc=[]
    for m in decoded:
        soc=1-m.energy_kwh/tables['types'].loc[m.uav_type].battery_energy_kwh
        charge=charge_time_s(soc,battery.loc[m.uav_type].full_charge_time_s)
        bc.append(dict(sortie_id=m.mission_id,battery_id=m.battery_id,takeoff_s=m.takeoff_s,return_s=m.return_s,return_soc=soc,charge_duration_s=charge,energy_ready_s=m.return_s+charge))
    pd.DataFrame(bc).to_csv(dest/'q2_battery_calendar.csv',index=False)
    old=tracer.RESULTS_Q2;loader=tracer.load_tables
    try:
        tracer.RESULTS_Q2=dest;tracer.load_tables=lambda:tables;tracer.build_trace().to_csv(dest/'transport_trace.csv',index=False)
    finally:tracer.RESULTS_Q2=old;tracer.load_tables=loader
    write(dest/'missions.json',[m.__dict__ for m in decoded]);write(dest/'metadata.json',metrics)
    return metrics

def main():
    tables=load_tables(); exact=exact_geometry(tables);exact.to_csv(OUT/'exact_geometry_sensitivity.csv',index=False)
    manifest={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((ROOT/'data/processed').glob('*')) if p.is_file()}
    write(OUT/'local_input_manifest.json',manifest)
    results=[]
    for name in ['run01','run02']:
        specs=import_specs(name);write(OUT/f'{name}_structure.json',specs)
        allboxes=[b for s in specs for bs in s['boxes_by_service'].values() for b in bs]
        assert len(allboxes)==len(set(allboxes))==80 and set(allboxes)==set(tables['boxes'].box_id)
        ev=MissionEvaluator(tables);missions=[];gates=[]
        for i,s in enumerate(specs,1):
            gs=GateStats();m=ev.evaluate_mission(s['uav_type'],s['boxes_by_service'],s['service_sequence'],gs)
            gates.append(dict(source_sortie_id=s['source_sortie_id'],**gs.__dict__))
            if m:m.mission_id=f'M{i:03d}';missions.append(m)
        write(OUT/f'{name}_structure_gates.json',gates)
        assert len(missions)==len(specs)
        decoded,info=joint_schedule(missions,tables)
        write(OUT/f'{name}_search.json',info);print(name,info,flush=True)
        if decoded is None:
            fallback=evaluate_solution(specs,ev,ResourceDecoder(tables))
            if fallback:decoded=fallback.decoded
        if decoded is not None:
            metrics=export(decoded,tables,OUT/'solutions'/name,name)
            export(decoded,tables,ROOT/'results/q2/pareto_schedules'/('XB01' if name=='run01' else 'XB02'),name)
            results.append(dict(name=name,**metrics));print(metrics,flush=True)
    write(OUT/'summary.json',results)

if __name__=='__main__':main()
