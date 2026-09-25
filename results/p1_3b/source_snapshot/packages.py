"""Materialize and independently verify autonomous pool representatives."""
import argparse,sys,time,math
from collections import defaultdict
import pandas as pd
from src.bench_p1_3b.common import *
from src.q2.evaluator import MissionEvaluator
from src.q3.e6_resources import color_intervals
from src.common.charging import charge_time_s
from src.xb1.audit import export

def materialize(trips,p,t):
    remaining={c:list(r['boxes']) for c,r in enumerate(p['classes'])};missions=[];ev=MissionEvaluator(t)
    for j,tr in enumerate(sorted(trips,key=lambda r:(r['pattern'],r['copy'])),1):
        r=p['patterns'][tr['pattern']];by=defaultdict(list)
        for c,n in r['counts']:
            assert len(remaining[c])>=n
            for _ in range(n):by[p['classes'][c]['key'][0]].append(remaining[c].pop(0))
        m=ev.evaluate_mission(r['type'],dict(by),r['sequence']);assert m
        assert abs(m.energy_kwh-r['energy'])<1e-7 and abs(m.relative_return_time-r['duration'])<1e-7
        m.mission_id=f'M{j:03d}';s=tr['start_units']/UNITS
        m.preparation_start_s=s;m.takeoff_s=s+m.relative_takeoff_time;m.return_s=s+m.relative_return_time
        m.delivery_times_s={k:s+v for k,v in m.relative_delivery_times.items()};missions.append(m)
    assert not any(remaining.values())
    for typ in 'ABC':
        group=[m for m in missions if m.uav_type==typ];bt=t['batteries'].set_index('uav_type').loc[typ]
        for kind in ('uav','battery'):
            rows=[]
            for i,m in enumerate(group):
                charge=charge_time_s(1-m.energy_kwh/t['types'].loc[typ].battery_energy_kwh,bt.full_charge_time_s)
                rows.append(dict(i=i,start=m.preparation_start_s if kind=='uav' else m.takeoff_s,end=m.return_s+(charge if kind=='battery' else 0)))
            ids=list(t['uavs'][t['uavs'].uav_type==typ].uav_id) if kind=='uav' else [f'BAT-{typ}-{i:02d}' for i in range(1,int(bt.battery_pool_count)+1)]
            color_intervals(rows,'start','end',ids,'resource')
            for row in rows:setattr(group[row['i']],kind+'_id',row['resource'])
    return missions

def workloads(missions,t):
    rows=[];bound=max(m.relative_return_time for m in missions)
    for typ in 'ABC':
        group=[m for m in missions if m.uav_type==typ];u=int((t['uavs'].uav_type==typ).sum());bt=t['batteries'].set_index('uav_type').loc[typ];b=int(bt.battery_pool_count)
        work=sum(m.relative_return_time for m in group);charges=[charge_time_s(1-m.energy_kwh/t['types'].loc[typ].battery_energy_kwh,bt.full_charge_time_s) for m in group]
        battery_work=sum(m.relative_return_time-m.relative_takeoff_time+c for m,c in zip(group,charges))
        lower=max(work/u,battery_work/b-max(charges,default=0));bound=max(bound,lower)
        rows.append(dict(type=typ,uavs=u,batteries=b,sorties=len(group),uav_occupation_s=work,battery_occupation_s=battery_work,uav_workload_lower_bound_s=work/u,battery_workload_lower_bound_s=battery_work/b-max(charges,default=0)))
    return dict(transport_workload_lower_bound_s=math.nextafter(bound,-math.inf),typed_loads=rows,scope='Any schedule of this fixed transport box/visit/type structure, independent of relay grouping')

def export_rep(run,ident,rank=0):
    dest=OUT/'q2/pareto_schedules'/ident
    if dest.exists():raise RuntimeError('Refuse overwrite representative '+ident)
    config=read(OUT/'transport_runs'/run/'config.json');rows=read(OUT/'transport_runs'/run/'candidate_structures.json')
    chosen=sorted(rows,key=lambda r:(r['objective_value'],r['structure_signature']))[rank]
    p=pool();t=tables();missions=materialize(chosen['trips'],p,t);metrics=export(missions,t,dest,ident)
    assert metrics['J_late']<=1e-4
    sys.path.insert(0,str(ROOT/'validation/mathematical'));from xb1_validate import check_package
    tick=time.process_time();validation=check_package(dest,ident,pd.read_csv(ROOT/'results/reset/geometry/route_geometry.csv',float_precision='round_trip'))
    record=dict(id=ident,origin_run=run,anchor=config['axis'],rank=rank,signature=chosen['structure_signature'],pattern_occurrences=[j['pattern'] for j in chosen['trips']],
        trips=chosen['trips'],metrics=metrics,package=str(dest.relative_to(ROOT)),validation_status=validation['status'],validation_cpu_s=time.process_time()-tick,
        validation_sha256=digest(dest/'validation.json'),pattern_pool_sha256=digest(OUT/'inputs/pattern_pool.json'),**workloads(missions,t))
    write(OUT/'representatives'/f'{ident}.json',record);print('TRANSPORT_VERIFIED',ident,metrics,flush=True);return record

def admit_historical(pid):
    """Readmit a known autonomous upper bound only after full pool membership."""
    import shutil
    p=pool();t=tables();src=ROOT/'results/reset/q2/pareto_schedules'/pid;ident='H_'+pid;dest=OUT/'q2/pareto_schedules'/ident
    if dest.exists():raise RuntimeError('Refuse overwrite historical readmission')
    bc={b:c for c,r in enumerate(p['classes']) for b in r['boxes']};lookup={pattern_key(r):i for i,r in enumerate(p['patterns'])};indices=[]
    for r in read(src/'missions.json'):
        key=(r['uav_type'],tuple(r['service_sequence']),tuple(sorted(Counter(bc[b] for b in r['box_ids']).items())))
        assert key in lookup;indices.append(lookup[key])
    shutil.copytree(src,dest);sys.path.insert(0,str(ROOT/'validation/mathematical'));from xb1_validate import check_package
    validation=check_package(dest,ident,pd.read_csv(ROOT/'results/reset/geometry/route_geometry.csv',float_precision='round_trip'))
    metrics=read(dest/'metadata.json');assert metrics['J_late']<=1e-4
    from types import SimpleNamespace
    missions=[SimpleNamespace(**r) for r in read(dest/'missions.json')]
    record=dict(id=ident,origin_run='HISTORICAL_AUTONOMOUS_FULL_POOL_READMISSION',anchor='HISTORICAL',signature=signature(sorted(indices)),pattern_occurrences=indices,
        metrics=metrics,package=str(dest.relative_to(ROOT)),validation_status=validation['status'],validation_sha256=digest(dest/'validation.json'),
        source_package=str(src.relative_to(ROOT)),source_hashes={f.name:digest(f) for f in src.iterdir() if f.is_file()},pattern_pool_sha256=digest(OUT/'inputs/pattern_pool.json'),**workloads(missions,t))
    write(OUT/'representatives'/f'{ident}.json',record);print('HISTORICAL_FULL_POOL_READMITTED',pid,metrics,flush=True);return record

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('run');a.add_argument('ident');a.add_argument('--rank',type=int,default=0);args=a.parse_args();install_input_guard();export_rep(args.run,args.ident,args.rank)
