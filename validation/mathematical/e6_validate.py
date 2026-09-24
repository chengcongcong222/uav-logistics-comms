#!/usr/bin/env python3
"""Independent E6 validator: no scheduler feasibility flags or routines used."""
from pathlib import Path
import argparse
import hashlib
import json
import math
import sys
import time

import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'validation/mathematical'))
from e52_validate_candidates import IndependentAudit,require
from src.q3.terrain_los import blocked_line_cells

Q3=ROOT/'results/q3';OUT=Q3/'e6';DATA=ROOT/'data/processed'


def read(path):return pd.read_csv(path,float_precision='round_trip')


def close(a,b,label,tol=1e-5):require(abs(float(a)-float(b))<=tol,f'{label}: {a} != {b}')


def charging(soc,full):
    require(0<=soc<=1,'SOC outside [0,1]')
    return full*(.65*(.9-soc)/.9+.35) if soc<.9 else full*.35*(1-soc)/.1


def union(windows):
    out=[]
    for a,b in sorted(windows):
        if out and a<=out[-1][1]+1e-8:out[-1][1]=max(out[-1][1],b)
        else:out.append([float(a),float(b)])
    return out


def no_overlap(rows,key,start,end,allowed):
    require(set(rows[key])<=set(allowed),f'Unknown resource {key}')
    for name,group in rows.groupby(key):
        previous=0.
        for row in group.sort_values(start).itertuples():
            a=float(getattr(row,start));b=float(getattr(row,end))
            require(a>=previous-1e-5,f'Overlap {name}: start {a} previous end {previous}')
            require(b>=a,'Negative occupied duration');previous=b


def validate_transport(pid,shifts):
    base=Q3.parent/'q2/pareto_schedules'/pid
    original=read(base/'q2_sorties.csv').set_index('sortie_id')
    flights=read(OUT/f'transport_sorties_{pid}.csv').set_index('sortie_id',drop=False)
    delivery=read(OUT/f'box_delivery_{pid}.csv').set_index('box_id',drop=False)
    old_delivery=read(base/'q2_box_delivery.csv').set_index('box_id')
    boxes=read(DATA/'boxes.csv').set_index('box_id')
    types=read(DATA/'transport_uav_types.csv').set_index('uav_type')
    uavs=read(DATA/'transport_uavs.csv').set_index('uav_id')
    batteries=read(DATA/'transport_batteries.csv').set_index('uav_type')
    geometry=read(DATA/'route_geometry.csv').set_index(['from_id','to_id'])
    require(len(delivery)==80 and delivery.index.is_unique and set(delivery.index)==set(boxes.index),'80-box coverage')
    require(set(flights.index)==set(original.index)==set(shifts),'Transport sortie identities')
    records=[];energy=0.;min_margin=float('inf')
    for sid,row in flights.iterrows():
        old=original.loc[sid];delta=shifts[sid]
        require(delta>=-1e-7,'Negative delay outside E6 search semantics')
        for field in ['uav_id','uav_type','battery_id','service_sequence']:require(row[field]==old[field],f'Changed transport structure {sid}/{field}')
        require(uavs.loc[row.uav_id].uav_type==row.uav_type,'UAV type mismatch')
        for field in ['preparation_start_s','takeoff_s','return_s']:close(row[field],old[field]+delta,f'Translation {sid}/{field}')
        bl=delivery[delivery.sortie_id==sid];old_bl=old_delivery[old_delivery.sortie_id==sid]
        require(set(bl.index)==set(old_bl.index),f'Changed grouping {sid}')
        p=types.loc[row.uav_type];mass=float(boxes.loc[bl.index].mass_kg.sum());volume=float(boxes.loc[bl.index].volume_m3.sum())
        require(mass<=p.max_payload_kg+1e-8 and volume<=p.cargo_volume_m3+1e-8,'Transport payload infeasible')
        require(row.takeoff_s>=row.preparation_start_s+p.prep_time_s+len(bl)*p.load_time_per_box_s-1e-6,'Prep/load incomplete')
        sequence=row.service_sequence.split('>');path=['O01']+sequence+['O01'];t=float(row.takeoff_s);e=0.;payload=mass
        for a,b in zip(path[:-1],path[1:]):
            g=geometry.loc[(a,b)];q=payload if b!='O01' else 0.
            equivalent=p.range_empty_m-(p.range_empty_m-p.range_full_m)*(q/p.max_payload_kg)**1.5
            e+=p.battery_energy_kwh*g.horizontal_distance_m/equivalent
            e+=(p.empty_mass_with_battery_kg+q)*9.80665*g.climb_height_m/(p.climb_energy_eff*3.6e6)
            require(p.descend_energy_eff==0,'Undefined transport descent rule')
            t+=g.climb_height_m/p.max_climb_mps+g.horizontal_distance_m/p.cruise_speed_mps+g.descent_height_m/p.max_descend_mps
            if b!='O01':
                batch=bl[bl.service_id==b];require(len(batch)>0,'Empty route stop')
                t+=p.handover_base_s+len(batch)*p.handover_per_box_s
                for boxid,box in batch.iterrows():
                    close(box.delivery_time_s,t,f'Delivery physics {boxid}')
                    close(box.delivery_time_s,old_delivery.loc[boxid].delivery_time_s+delta,'Delivery translation')
                    require(boxes.loc[boxid].service_id==b,'Wrong destination')
                payload-=boxes.loc[batch.index].mass_kg.sum()
        close(t,row.return_s,f'Transport return {sid}');close(e,row.energy_kwh,f'Transport energy {sid}')
        margin=(1-p.return_soc_min_pct/100)*p.battery_energy_kwh-e
        require(margin>=-1e-7,'Transport reserve');min_margin=min(min_margin,margin);energy+=e
        soc=1-e/p.battery_energy_kwh
        charge=charging(soc,batteries.loc[row.uav_type].full_charge_time_s)
        records.append(dict(sortie_id=sid,battery_id=row.battery_id,takeoff_s=row.takeoff_s,return_s=row.return_s,
                            energy_ready_s=row.return_s+charge,return_soc=soc))
    no_overlap(flights.reset_index(drop=True),'uav_id','preparation_start_s','return_s',uavs.index)
    battery_ids=[f'BAT-{g}-{i:02d}' for g,r in batteries.iterrows() for i in range(1,int(r.battery_pool_count)+1)]
    no_overlap(pd.DataFrame(records),'battery_id','takeoff_s','energy_ready_s',battery_ids)
    declared=read(OUT/f'transport_battery_calendar_{pid}.csv').set_index('sortie_id')
    require(declared.index.is_unique and set(declared.index)==set(flights.index),'Transport battery calendar coverage')
    for row in records:
        for field in ['takeoff_s','return_s','energy_ready_s','return_soc']:close(row[field],declared.loc[row['sortie_id'],field],'Transport battery calendar')
    late=norm=weight=0.;violations=[]
    for bid,r in delivery.iterrows():
        box=boxes.loc[bid];t=r.delivery_time_s
        if box.is_medical and t>box.expected_deadline_s+1e-5:violations.append(bid)
        if box.is_first_batch and t>box.first_deadline_s+1e-5:violations.append(bid)
        late+=box.priority_weight*max(0.,t-box.expected_deadline_s)
        norm+=box.priority_weight*t/box.expected_deadline_s;weight+=box.priority_weight
    require(not violations,f'Hard deadline violations {violations}')
    return dict(J_late=late,J_norm=norm/weight,transport_energy_kwh=energy,
                transport_makespan_s=float(flights.return_s.max()),transport_sorties=len(flights),
                minimum_transport_energy_margin_kwh=min_margin,hard_deadline_violations=0),flights


def validate_plan(pid,step=0.5):
    tick=time.monotonic();checker=IndependentAudit()
    manifest=json.loads((OUT/'input_manifest.json').read_text())
    for f,h in manifest['hashes'].items():require(hashlib.sha256((ROOT/f).read_bytes()).hexdigest()==h,f'Changed input {f}')
    shifts=read(OUT/f'transport_shifts_{pid}.csv').set_index('sortie_id').shift_s.to_dict()
    transport,flights=validate_transport(pid,shifts)
    rows=read(OUT/f'relay_sorties_{pid}.csv')
    sites=read(OUT/f'candidate_sites_{pid}.csv').set_index('site_id')
    atoms=read(OUT/'guarded_atomic_tasks.csv');atoms=atoms[atoms.pareto_id==pid].set_index('atomic_task_id')
    inherited=read(Q3/'relay_atomic_tasks_e52.csv').set_index('atomic_task_id')
    require(set(atoms.index)==set(inherited[inherited.pareto_id==pid].index),'Guard changed gap identities')
    for aid,t in atoms.iterrows():
        old=inherited.loc[aid];flight=flights.loc[t.transport_sortie_id];delta=shifts[t.transport_sortie_id]
        require(t.transport_sortie_id==old.transport_sortie_id,'Guard changed sortie')
        close(t.service_start_s,max(flight.takeoff_s-delta,old.service_start_s-2),'Guard start')
        close(t.service_end_s,min(flight.return_s-delta,old.service_end_s+2),'Guard end')
    guarantee=read(OUT/f'communication_guarantee_{pid}.csv')
    require(guarantee.atomic_task_id.is_unique and set(guarantee.atomic_task_id)==set(atoms.index),'Exactly one relay assignment per gap')
    require(set(guarantee.topology)=={'TRANSPORT_RELAY_G01'} and (guarantee.provider_count==1).all(),'Illegal relay topology')
    declared_uav=read(OUT/f'relay_uav_calendar_{pid}.csv').set_index('relay_sortie_id')
    declared_ec=read(OUT/f'relay_energy_calendar_{pid}.csv').set_index('relay_sortie_id')
    require(rows.relay_sortie_id.is_unique,'Duplicate relay sorties')
    for calendar in [declared_uav,declared_ec]:
        require(calendar.index.is_unique and set(calendar.index)==set(rows.relay_sortie_id),'Relay calendar coverage')
    relay_energy=0.;min_margin=float('inf');min_mc=float('inf');seen=[]
    checked_candidates=[];radio_cache={}
    full_charge=float(read(DATA/'relay_energy_components.csv').iloc[0].full_charge_time_s)
    for r in rows.itertuples():
        s=sites.loc[r.site_id];ids=json.loads(r.task_ids);seen.extend(ids);windows=[]
        lon,lat=checker.tf.transform(s.x_m,s.y_m);ground=checker.dem.sample(lon,lat)
        close(s.ground_elevation_m,ground,'Relay DEM');close(s.z_amsl_m,ground+s.agl_m,'Relay AGL')
        require(0<s.agl_m<=checker.params['max_agl_m'],'Relay height')
        rg=checker.backhaul(s);require(rg>=0,'Relay backhaul outage')
        for aid in ids:
            task=atoms.loc[aid];shift=shifts[task.transport_sortie_id]
            window=(task.service_start_s+shift,task.service_end_s+shift);windows.append(window)
            pair=guarantee[guarantee.atomic_task_id==aid].iloc[0]
            require(pair.relay_sortie_id==r.relay_sortie_id and pair.relay_id==r.relay_id and pair.site_id==r.site_id,'Guarantee assignment mismatch')
            close(pair.service_start_s,window[0],'Shifted gap start');close(pair.service_end_s,window[1],'Shifted gap end')
            margin=checker.interval((pid,task.transport_sortie_id),s,task.service_start_s,task.service_end_s,step=step)
            require(margin>=0,f'Relay access outage {aid}')
            min_mc=min(min_mc,margin,rg)
            checked_candidates.append(dict(atomic_task_id=aid,site_id=r.site_id,min_access_margin_db=margin,backhaul_margin_db=rg))
        merged=union(windows);a=merged[0][0];b=merged[-1][1];active=sum(y-x for x,y in merged);idle=b-a-active
        expected=checker.energy(s,active);idle_energy=checker.params['hover_power_kw']*idle/3600
        total=expected['total_energy_kwh']+idle_energy
        margin=(1-checker.params['rho'])*checker.params['energy_kwh']-total
        require(margin>=-1e-7,'Merged relay energy infeasible');min_margin=min(min_margin,margin)
        for field,value in [('active_communication_s',active),('idle_hover_s',idle),('idle_energy_kwh',idle_energy),
                            ('flight_energy_kwh',expected['flight_energy_kwh']),('setup_energy_kwh',expected['setup_energy_kwh']),
                            ('active_energy_kwh',expected['service_energy_kwh']),('total_energy_kwh',total),('energy_margin_kwh',margin),
                            ('service_start_s',a),('service_end_s',b)]:close(getattr(r,field),value,f'Relay {field}')
        arrival=a-checker.params['setup_time_s'];takeoff=arrival-expected['outbound_time_s']
        prep=takeoff-checker.params['prep_time_s'];ret=b+expected['return_time_s']
        soc=1-total/checker.params['energy_kwh'];ready=ret+charging(soc,full_charge)
        for field,value in [('preparation_start_s',prep),('takeoff_s',takeoff),('arrival_s',arrival),('return_s',ret),
                            ('uav_available_s',ret+checker.params['turnaround_time_s']),('return_soc',soc),('energy_ready_s',ready)]:close(getattr(r,field),value,f'Relay clock {field}')
        require(prep>=-1e-6,'Relay must not prepare before time zero')
        u=declared_uav.loc[r.relay_sortie_id];ec=declared_ec.loc[r.relay_sortie_id]
        require(u.relay_id==r.relay_id and ec.energy_component_id==r.energy_component_id,'Calendar IDs')
        close(u.busy_start_s,prep,'UAV occupancy start');close(u.busy_end_s,ret+300,'UAV turnaround')
        close(ec.soc_at_takeoff,1.,'Full energy at takeoff');close(ec.return_soc,soc,'Return SOC')
        close(ec.takeoff_s,takeoff,'Component takeoff');close(ec.return_s,ret,'Component return');close(ec.charge_end_s,ready,'Recharge completion')
        relay_energy+=total
    require(len(seen)==len(set(seen)) and set(seen)==set(atoms.index),'Atomic task partition')
    no_overlap(rows,'relay_id','preparation_start_s','uav_available_s',['R01','R02'])
    no_overlap(rows,'energy_component_id','takeoff_s','energy_ready_s',[f'REC-{i:02d}' for i in range(1,7)])
    # Full-flight validation includes direct portions, not only inherited gaps.
    bad=[];full_samples=0;relayed_samples=0;direct_samples=0;full_refinements=0
    for sid,flight in flights.iterrows():
        shift=shifts[sid];tt,_=checker.traces[pid,sid]
        lo=flight.takeoff_s;hi=flight.return_s
        times=set(np.arange(math.ceil(lo/step),math.floor(hi/step)+1)*step)
        times.update(t+shift for t in tt if lo-1e-7<=t+shift<=hi+1e-7);times.update([lo,hi])
        assignments=guarantee[guarantee.transport_sortie_id==sid]
        times.update(assignments.service_start_s);times.update(assignments.service_end_s)
        direct_cache={}
        def direct_at(t):
            if t in direct_cache:return direct_cache[t]
            xyz=checker.position((pid,sid),t-shift);ll=checker.tf.transform(*xyz[:2])
            blocked=blocked_line_cells(checker.dem,*ll,xyz[2],*checker.gateway_ll)
            dist=float(np.linalg.norm(xyz-checker.gateway))
            direct=checker.budgets['transport<->G01']-32.45-20*math.log10(checker.radio.f_mhz)-20*math.log10(max(dist,1e-6)/1000)-checker.radio.l_obs_db*blocked
            direct_cache[t]=(direct,bool(blocked),xyz)
            return direct_cache[t]
        coarse=sorted(times);pending=[]
        for a,b in zip(coarse[:-1],coarse[1:]):
            va=direct_at(a);vb=direct_at(b)
            if va[1]!=vb[1] or (va[0]>=0)!=(vb[0]>=0):pending.append((a,b))
        while pending:
            a,b=pending.pop()
            if b-a<=.1:continue
            mid=(a+b)/2;times.add(mid);full_refinements+=1
            for x,y in [(a,mid),(mid,b)]:
                vx=direct_at(x);vy=direct_at(y)
                if vx[1]!=vy[1] or (vx[0]>=0)!=(vy[0]>=0):pending.append((x,y))
        for t in sorted(times):
            direct,_,xyz=direct_at(t)
            full_samples+=1
            if direct>=0:direct_samples+=1;continue
            covering=assignments[(assignments.service_start_s<=t+1e-7)&(assignments.service_end_s>=t-1e-7)]
            if len(covering)!=1:
                bad.append(dict(sortie_id=sid,time_s=float(t),reason='NO_UNIQUE_ASSIGNED_RELAY',direct_margin_db=direct));continue
            assignment=covering.iloc[0];s=sites.loc[assignment.site_id]
            value,_=checker.link(xyz,s)
            if value<0:bad.append(dict(sortie_id=sid,time_s=float(t),reason='RELAY_ACCESS_NEGATIVE',access_margin_db=value))
            else:relayed_samples+=1
    pd.DataFrame(bad,columns=['sortie_id','time_s','reason','direct_margin_db','access_margin_db']).to_csv(OUT/f'communication_violations_{pid}_{step}.csv',index=False)
    require(not bad,f'{len(bad)} full-flight communication violations; see audit CSV')
    metrics=json.loads((OUT/f'joint_metrics_{pid}.json').read_text())
    for field in ['J_late','J_norm','transport_energy_kwh']:close(metrics[field],transport[field],field,1e-4)
    close(metrics['relay_energy_kwh'],relay_energy,'Relay total energy')
    close(metrics['total_energy_kwh'],relay_energy+transport['transport_energy_kwh'],'Joint energy')
    makespan=max(transport['transport_makespan_s'],float(rows.return_s.max()))
    close(metrics['joint_makespan_s'],makespan,'Joint makespan')
    close(metrics['total_transport_shift_s'],sum(shifts.values()),'Total shift')
    close(metrics['max_transport_shift_s'],max(shifts.values()),'Maximum shift')
    close(metrics['minimum_M_E_kwh'],min_margin,'Minimum relay energy margin')
    pd.DataFrame(checked_candidates).to_csv(OUT/f'independent_candidate_audit_{pid}_{step}.csv',index=False)
    result=dict(pareto_id=pid,status='E6_PLAN_INDEPENDENTLY_VALIDATED',step_s=step,hard_violations=0,
                uncovered_sample_count=0,communication_uncovered_duration_s=0.,full_flight_samples=full_samples,
                direct_samples=direct_samples,relayed_samples=relayed_samples,relay_sorties=len(rows),
                full_flight_boundary_refinements=full_refinements,boundary_refinement_s=.1,
                relay_ids=sorted(rows.relay_id.unique()),energy_components=sorted(rows.energy_component_id.unique()),
                minimum_relay_energy_margin_kwh=min_margin,minimum_twohop_margin_db=min_mc,
                runtime_s=time.monotonic()-tick,
                limitation='Numerical whole-flight sampling including phase and gap boundaries; not analytic continuous-time proof')
    result.update(transport)
    if step==.5:
        metrics['communication_uncovered_duration_s']=0.;metrics['communication_validation']=result['status']
        (OUT/f'joint_metrics_{pid}.json').write_text(json.dumps(metrics,indent=2)+'\n')
    artifacts=[OUT/f'{stem}_{pid}.csv' for stem in ['transport_sorties','box_delivery','transport_shifts',
               'transport_uav_calendar','transport_battery_calendar','relay_sorties','relay_uav_calendar',
               'relay_energy_calendar','communication_guarantee','candidate_sites','guarded_selected_pairs']]
    artifacts += [OUT/'guarded_atomic_tasks.csv',OUT/f'joint_metrics_{pid}.json']
    result['artifact_sha256']={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in artifacts}
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--plan',required=True);parser.add_argument('--step',type=float,default=.5)
    args=parser.parse_args();target=OUT/f'validation_{args.plan}_{args.step}.json'
    try:
        result=validate_plan(args.plan,args.step)
        target.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2),flush=True)
    except Exception as exc:
        target.write_text(json.dumps(dict(status='E6_PLAN_VALIDATION_FAILED',error=str(exc)),indent=2)+'\n');raise
