"""Separate exact-cell DEM sensitivity; frozen scientific authority unchanged."""
import copy,json,math,sys
import numpy as np
import pandas as pd
from src.xb1.audit import ROOT,OUT,load_tables,MissionEvaluator,charge_time_s,export,write
from src.common.terrain import Dem
sys.path.insert(0,str(ROOT/'validation/mathematical'))
from xb1_validate import check_package

def verify_geometry(geometry,tables):
    # Independent row-strip clipping traversal, versus generator grid-event sweep.
    dem=Dem();nodes=tables['nodes'].set_index('node_id');inv=~dem.transform;checked=0
    for g in geometry.itertuples():
        a=nodes.loc[g.from_id];b=nodes.loc[g.to_id];x0,y0=inv*(a.longitude,a.latitude);x1,y1=inv*(b.longitude,b.latitude)
        dx=x1-x0;dy=y1-y0;cells=set()
        for r in range(math.floor(min(y0,y1)-1e-9),math.floor(max(y0,y1)+1e-9)+1):
            if abs(dy)<1e-12:
                if not r-1e-9<=y0<=r+1+1e-9:continue
                low,high=0.,1.
            else:
                u,v=sorted([(r-y0)/dy,(r+1-y0)/dy]);low=max(0,u);high=min(1,v)
                if low>high+1e-10:continue
            xa,xb=sorted([x0+low*dx,x0+high*dx])
            for c in range(math.floor(xa-1e-9),math.floor(xb+1e-9)+1):
                if 0<=r<dem.arr.shape[0] and 0<=c<dem.arr.shape[1]:cells.add((r,c))
        value=max(float(dem.arr[r,c]) for r,c in cells)
        assert abs(value-g.max_dem_elevation_m)<1e-7,(g.from_id,g.to_id,value,g.max_dem_elevation_m)
        checked+=1
    return dict(status='EXACT_CELL_GEOMETRY_CROSSCHECK_PASS',legs=checked,method='independent row-strip clipping vs grid boundary events',interpretation='Affine lon/lat segment through native raster cells; no interpolation or DEM resampling')

def main():
    t=load_tables();geometry=pd.read_csv(OUT/'exact_geometry_sensitivity.csv',float_precision='round_trip')
    write(OUT/'exact_geometry_validation.json',verify_geometry(geometry,t))
    t['geom']=geometry;ev=MissionEvaluator(t);full=t['batteries'].set_index('uav_type');rows=[]
    for pid in ['P01','P02','P03','XB01','XB02']:
        base=ROOT/'results/q2/pareto_schedules'/pid;fl=pd.read_csv(base/'q2_sorties.csv');boxes=pd.read_csv(base/'q2_box_delivery.csv');missions={};fail=[]
        for r in fl.itertuples():
            groups={s:list(g.box_id) for s,g in boxes[boxes.sortie_id==r.sortie_id].groupby('service_id')}
            m=ev.evaluate_mission(r.uav_type,groups,r.service_sequence.split('>'))
            if m is None:fail.append(r.sortie_id);continue
            m.mission_id=r.sortie_id;m.uav_id=r.uav_id;m.battery_id=r.battery_id;missions[r.sortie_id]=m
        if fail:
            rows.append(dict(pareto_id=pid,status='EXACT_DEM_STATIC_GATE_FAILED',sorties=fail));continue
        edges=[]
        for kind,field,key in [('UAV','uav_id','preparation_start_s'),('BATTERY','battery_id','takeoff_s')]:
            for _,group in fl.groupby(field):
                rr=list(group.sort_values(key).itertuples())
                for a,b in zip(rr[:-1],rr[1:]):
                    ma,mb=missions[a.sortie_id],missions[b.sortie_id];gap=ma.relative_return_time
                    if kind=='BATTERY':gap+=charge_time_s(1-ma.energy_kwh/t['types'].loc[ma.uav_type].battery_energy_kwh,full.loc[ma.uav_type].full_charge_time_s)-mb.relative_takeoff_time
                    edges.append((a.sortie_id,b.sortie_id,gap+1e-5))
        starts={r.sortie_id:max(r.preparation_start_s,r.takeoff_s-missions[r.sortie_id].relative_takeoff_time) for r in fl.itertuples()}
        for it in range(len(starts)+1):
            changed=False
            for a,b,gap in edges:
                if starts[b]<starts[a]+gap-1e-8:starts[b]=starts[a]+gap;changed=True
            if not changed:break
        assert not changed,'Positive precedence cycle'
        for sid,m in missions.items():
            s=starts[sid];m.preparation_start_s=s;m.takeoff_s=s+m.relative_takeoff_time;m.return_s=s+m.relative_return_time;m.delivery_times_s={b:s+v for b,v in m.relative_delivery_times.items()}
            if m.hard_deadline_latest_start is not None and s>m.hard_deadline_latest_start+1e-5:fail.append(sid)
        if fail:
            rows.append(dict(pareto_id=pid,status='FIXED_ORDER_RETIMING_HARD_DEADLINE_FAILURE_NOT_STRUCTURAL_PROOF',sorties=fail));continue
        dest=OUT/'dem_sensitivity/q2/pareto_schedules'/pid
        metrics=export(list(missions.values()),t,dest,pid+'_exact_cells');checked=check_package(dest,pid,geometry)
        rows.append(dict(pareto_id=pid,status=checked['status'],**metrics,maximum_start_delay_s=max(starts[r.sortie_id]-r.preparation_start_s for r in fl.itertuples()),maximum_takeoff_delay_s=max(missions[r.sortie_id].takeoff_s-r.takeoff_s for r in fl.itertuples()),interpretation='Exact-cell heights plus earliest delay-only repair preserving original UAV/battery orders and original takeoff lower bounds; preparation waits compressed; not reoptimized'))
    write(OUT/'dem_sensitivity_summary.json',rows);print(json.dumps(rows,indent=2),flush=True)
if __name__=='__main__':main()
