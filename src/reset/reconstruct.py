"""A bounded dependency-driven structure neighborhood, accepted on full Q3 metrics.

Enumerate local box repartitions/types/routes; each retained structural branch
releases all absolute clocks, UAV/battery allocation and relay grouping/order.
This is an explicitly incomplete union of joint MILPs, not a global certificate.
"""
import copy,itertools,json,time
import pandas as pd
from src.reset.geometry import ROOT,OUT,tables,write
from src.reset.q3 import configure,ResetEngine,export_new
from src.q3.e7_core import objective_key
from src.q3.e8_seed_variants import partition
from src.q3.e7_pareto import dominates
from src.xb1.q3 import joint_order
from src.xb1.audit import export
from src.q2.evaluator import MissionEvaluator
from src.q2.mission import Mission

def run(pid='A03'):
    configure();candidates=[]
    for p in (OUT/'q3'/pid/'solutions').glob('*/witness.json'):candidates.append(json.loads(p.read_text()))
    seed=min(candidates,key=lambda x:objective_key(x,'timeliness'));source={m['mission_id']:m for m in json.loads((OUT/'q2/pareto_schedules'/pid/'missions.json').read_text())}
    atoms=pd.read_csv(OUT/'q3'/pid/'guarded_atomic_tasks.csv').set_index('atomic_task_id');pairs=[]
    for r in sorted(seed['selected'],key=lambda r:-r['active_communication_s']):
        ids=sorted({atoms.loc[a].transport_sortie_id for a in r['task_ids']})
        for a,b in itertools.combinations(ids,2):
            boxes=source[a]['box_ids']+source[b]['box_ids'];services=set(source[a]['service_sequence']+source[b]['service_sequence'])
            if len(boxes)<=10 and len(services)<=3:pairs.append((a,b,r['site_id'],r['active_communication_s']))
    assert pairs,'No configured two-sortie dependency neighborhood'
    ev=MissionEvaluator(tables());record=[];alternatives=[]
    for a,b,site,active in pairs[:3]:
        ids=sorted(source[a]['box_ids']+source[b]['box_ids']);full=(1<<len(ids))-1;patterns={}
        for mask in range(1,full+1):
            by={}
            for j,bid in enumerate(ids):
                if mask>>j&1:by.setdefault(ev.box_idx.loc[bid].service_id,[]).append(bid)
            options=[]
            for seq in itertools.permutations(sorted(by)):
                for typ in ev.types.index:
                    m=ev.evaluate_mission(typ,by,list(seq))
                    if m:options.append(m)
            patterns[mask]=options
        local=[]
        for mask in range(1,full):
            if not mask&1:continue
            for x,y in itertools.product(patterns[mask],patterns[full^mask]):
                if x.energy_kwh+y.energy_kwh>source[a]['energy_kwh']+source[b]['energy_kwh']+.5:continue
                identity=lambda m:(m.uav_type,tuple(m.service_sequence),tuple(sorted(m.box_ids)))
                old={(source[s]['uav_type'],tuple(source[s]['service_sequence']),tuple(sorted(source[s]['box_ids']))) for s in [a,b]}
                if {identity(x),identity(y)}==old:continue
                hard=sum(float(ev.box_idx.loc[bid].priority_weight)*m.relative_delivery_times[ev.box_idx.loc[bid].service_id] for m in [x,y] for bid in m.box_ids if ev.hard_deadline(bid) is not None)
                local.append((hard,x.energy_kwh+y.energy_kwh,x.relative_return_time+y.relative_return_time,x,y))
        record.append(dict(sorties=[a,b],shared_relay_site=site,active_communication_s=active,boxes=ids,feasible_local_pairs=len(local),masks=full))
        if local:
            best=min(local,key=lambda x:x[:3]);alternatives.append((a,b,best[3:5]));break
    if not alternatives:
        write(OUT/f'structural_neighborhood_{pid}.json',dict(status='NO_ALTERNATIVE_IN_CONFIGURED_LOCAL_PAIRS',records=record,scope='first three shared-relay two-sortie subsets, ten boxes, three services, energy increase at most 0.5 kWh',infeasibility_proven=False));return
    a,b,xy=alternatives[0];log=[]
    # Two independently ranked local choices would consume more budget. This
    # first bounded experiment evaluates one complete structural replacement.
    newpid='AN01';missions=[]
    for sid,m in source.items():
        item=copy.deepcopy(xy[0] if sid==a else xy[1] if sid==b else Mission(**m));item.mission_id=sid
        item.preparation_start_s=0.;item.takeoff_s=item.relative_takeoff_time;item.return_s=item.relative_return_time;item.delivery_times_s=dict(item.relative_delivery_times)
        item.uav_id=list(tables()['uavs'][tables()['uavs'].uav_type==item.uav_type].uav_id)[0];item.battery_id=f'BAT-{item.uav_type}-01';missions.append(item)
    p=OUT/'q2/pareto_schedules'/newpid;export(missions,tables(),p,newpid)
    write(p/'template_status.json',dict(status='RELATIVE_Q3_STRUCTURE_TEMPLATE_NOT_AN_EXECUTABLE_Q2_SCHEDULE',source=pid,changed_sorties=[a,b],clocks_and_resource_ids_are_placeholders=True))
    e=ResetEngine(newpid);e.pool();order=sorted(source,key=lambda s:source[s]['preparation_start_s']+seed['shifts'][s]);groups=[]
    for start in range(0,len(order),8):
        ids=list(e.atoms[e.atoms.transport_sortie_id.isin(order[start:start+8])].atomic_task_id)
        if ids:groups+=partition(e,ids,'unit')
    tick=time.monotonic();answer,info=joint_order(e,groups,limit=60)
    info.update(source=pid,target=newpid,changed_sorties=[a,b],all_transport_clocks_and_resources_released=True,relay_group_site_order_and_energy_rebuilt=True,dependency_neighborhood=record,domain='one selected two-sortie structure replacement; joint resource MILP, finite sites',global_optimum_proven=False)
    if answer:
        export_new(e,answer,newpid+'_Q3_001');info.update(metrics=answer['metrics'],dominates_source=dominates(answer['metrics'],seed['metrics']),source_metrics=seed['metrics'])
    write(OUT/'structural_reconstruction.json',info);print(info,flush=True)

if __name__=='__main__':
    import sys
    run(sys.argv[1] if len(sys.argv)>1 else 'A03')
