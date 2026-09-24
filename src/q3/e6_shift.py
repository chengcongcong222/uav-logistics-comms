"""Level C: continuous minimum-delay MILP for a chosen relay task partition.

Only transport time translations are allowed. Routes, box assignment, types,
transport UAV/battery IDs and their original orders remain unchanged. A result
is optimal only within the chosen candidate sites/task groups and these orders.
"""
from __future__ import annotations
import time
import numpy as np
from scipy.optimize import Bounds,LinearConstraint,milp
from scipy.sparse import coo_matrix

from src.q3.e6_resources import read,PROCESSED_DIR,RESULTS_Q2,charge_time_s,sortie_column,color_intervals


def transport_unit_partitions(engine,pid,max_variants=4):
    """Avoid binding independently delayed later sorties into the same hover.

    Keep each transport sortie's nearby gaps together when a common site exists;
    jointly cover only the initial hard-deadline transport units. Later units
    remain separate, so shifts cannot induce long artificial hover bridges.
    """
    transport,limits,_=shift_transport_constraints(pid)
    by_transport={}
    for aid in engine.edges[pid]:by_transport.setdefault(engine.atoms.loc[aid].transport_sortie_id,[]).append(aid)
    common={s:set.intersection(*(set(engine.edges[pid][a]) for a in ids)) for s,ids in by_transport.items()}
    if any(not c for c in common.values()):return []
    critical=[s for s in by_transport if transport.loc[s].preparation_start_s<1e-7 and limits[s]<3000]
    others=[s for s in by_transport if s not in critical]
    site_ids=sorted(set.union(*(common[s] for s in critical)))
    masks={sid:sum(1<<i for i,s in enumerate(critical) if sid in common[s]) for sid in site_ids}
    target=(1<<len(critical))-1;pairs=[]
    def cost(sid):
        en=engine.energy(engine.sites[sid],0)
        return en['outbound_time_s']+en['return_time_s']
    for i,a in enumerate(site_ids):
        for b in site_ids[i:]:
            if masks[a]|masks[b]==target:pairs.append((cost(a)+cost(b),a,b))
    pairs.sort();variants=[]
    for _,a,b in pairs[:max_variants]:
        grouped={a:[],b:[]}
        for s in critical:
            sid=min([sid for sid in [a,b] if sid in common[s]],key=cost)
            grouped[sid].extend(by_transport[s])
        groups=[dict(site_id=sid,task_ids=ids) for sid,ids in grouped.items() if ids]
        for s in others:
            sid=min(common[s],key=cost)
            groups.append(dict(site_id=sid,task_ids=by_transport[s]))
        variants.append(groups)
    return variants


def shift_transport_constraints(pid):
    base=RESULTS_Q2/'pareto_schedules'/pid
    transport=read(base/'q2_sorties.csv').set_index('sortie_id',drop=False)
    boxes=read(base/'q2_box_delivery.csv')
    types=read(PROCESSED_DIR/'transport_uav_types.csv').set_index('uav_type')
    batteries=read(PROCESSED_DIR/'transport_batteries.csv').set_index('uav_type')
    limits={sid:20000. for sid in transport.index}
    for r in boxes.itertuples():
        if np.isfinite(r.hard_deadline_s):limits[r.sortie_id]=min(limits[r.sortie_id],r.hard_deadline_s-r.delivery_time_s)
    precedence=[]
    for _,group in transport.groupby('uav_id'):
        rows=list(group.sort_values('preparation_start_s').itertuples())
        for a,b in zip(rows[:-1],rows[1:]):precedence.append((a.sortie_id,b.sortie_id,a.return_s-b.preparation_start_s,'UAV'))
    for _,group in transport.groupby('battery_id'):
        rows=list(group.sort_values('takeoff_s').itertuples())
        for a,b in zip(rows[:-1],rows[1:]):
            soc=1-a.energy_kwh/types.loc[a.uav_type].battery_energy_kwh
            ready=a.return_s+charge_time_s(soc,batteries.loc[a.uav_type].full_charge_time_s)
            precedence.append((a.sortie_id,b.sortie_id,ready-b.takeoff_s,'BATTERY'))
    return transport,limits,precedence


def optimize_shifts(engine,pid,groups,time_limit=90):
    transport,limits,precedence=shift_transport_constraints(pid)
    ids=list(transport.index);idx={s:i for i,s in enumerate(ids)};n=len(ids);k=len(groups)
    costs=[1.]*n;low=[0.]*n;high=[max(0,limits[s]) for s in ids];integer=[0]*n
    def variable(lo,hi,kind=0,cost=0):
        j=len(costs);costs.append(cost);low.append(lo);high.append(hi);integer.append(kind);return j
    starts=[];ends=[];assign=[];leads=[];tails=[]
    for group in groups:
        en=engine.energy(engine.sites[group['site_id']],0)
        lead=engine.pr['prep_time_s']+en['outbound_time_s']+engine.pr['setup_time_s']
        tail=en['return_time_s']+engine.pr['turnaround_time_s']
        starts.append(variable(lead,40000));ends.append(variable(lead,40000));leads.append(lead);tails.append(tail)
        assign.append([variable(0,1,1),variable(0,1,1)])
    maxshift=variable(0,20000)
    rows=[];lbs=[];ubs=[]
    def constraint(values,lo=-np.inf,hi=np.inf):rows.append(values);lbs.append(lo);ubs.append(hi)
    for a,b,gap,_ in precedence:constraint({idx[b]:1,idx[a]:-1},lo=gap)
    for i in range(n):constraint({maxshift:1,i:-1},lo=0)
    for j,group in enumerate(groups):
        constraint({assign[j][0]:1,assign[j][1]:1},lo=1,hi=1)
        for aid in group['task_ids']:
            task=engine.atoms.loc[aid];d=idx[task.transport_sortie_id]
            constraint({starts[j]:1,d:-1},hi=float(task.service_start_s))
            constraint({ends[j]:1,d:-1},lo=float(task.service_end_s))
        en=engine.energy(engine.sites[group['site_id']],0)
        # Conservative all-hover communication activation for this MILP only;
        # actual active/idle union energy is recalculated for final sorties.
        maxspan=((1-engine.pr['rho'])*engine.pr['energy_kwh']-en['total_energy_kwh'])*3600/(engine.pr['hover_power_kw']+engine.pr['comm_power_kw'])
        constraint({ends[j]:1,starts[j]:-1},lo=0,hi=maxspan)
    big=60000.
    for i in range(k):
        for j in range(i+1,k):
            for r in range(2):
                z=variable(0,1,1)
                # end_i + tail_i <= start_j - lead_j if both use r and z=1.
                constraint({ends[i]:1,starts[j]:-1,z:big,assign[i][r]:big,assign[j][r]:big},hi=3*big-tails[i]-leads[j])
                constraint({ends[j]:1,starts[i]:-1,z:-big,assign[i][r]:big,assign[j][r]:big},hi=2*big-tails[j]-leads[i])
    # Identical relays: eliminate the global swap symmetry.
    low[assign[0][0]]=high[assign[0][0]]=1
    def solve(c,time_limit):
        rr=[];cc=[];vv=[]
        for i,row in enumerate(rows):
            for j,value in row.items():rr.append(i);cc.append(j);vv.append(value)
        a=coo_matrix((vv,(rr,cc)),shape=(len(rows),len(costs))).tocsc()
        return milp(np.array(c),integrality=np.array(integer),bounds=Bounds(np.array(low),np.array(high)),
                    constraints=LinearConstraint(a,np.array(lbs),np.array(ubs)),
                    options=dict(time_limit=time_limit,mip_rel_gap=1e-6))
    tick=time.monotonic();result=solve(costs,time_limit)
    info=dict(status=int(result.status),message=str(result.message),groups=k,
              runtime_s=time.monotonic()-tick,total_shift_s=None if result.fun is None else float(result.fun),
              dual_bound=None if getattr(result,'mip_dual_bound',None) is None else float(result.mip_dual_bound),
              mip_gap=None if getattr(result,'mip_gap',None) is None else float(result.mip_gap),
              scope='FIXED_RELAY_GROUPS_SITES_AND_ORIGINAL_TRANSPORT_RESOURCE_ORDERS',
              conservative_energy_bound=True,component_check='POSTSOLVE_EXACT_INTERVAL_COLORING')
    if result.x is None:return None,None,info
    # Lexicographic second stage within the best attained total delay.
    best=result.x.copy();sumshift=sum(best[:n])
    constraint({i:1 for i in range(n)},hi=sumshift+1e-5)
    second=[0.]*len(costs);second[maxshift]=1
    refined=solve(second,min(30,time_limit))
    if refined.x is not None:best=refined.x
    shifts={sid:max(0.,float(best[i])) for i,sid in enumerate(ids)}
    selected=[]
    for j,group in enumerate(groups):
        col=sortie_column(engine,pid,group['site_id'],group['task_ids'],shifts)
        if col is None:raise ValueError('Shift MILP energy/timing mismatch')
        selected.append(col)
    try:
        color_intervals(selected,'preparation_start_s','uav_available_s',['R01','R02'],'relay_id')
        color_intervals(selected,'takeoff_s','energy_ready_s',[f'REC-{i:02d}' for i in range(1,7)],'energy_component_id')
    except ValueError as exc:
        info['postsolve_resource_failure']=str(exc)
        return None,None,info
    info.update(max_shift_s=max(shifts.values()),total_shift_s=sum(shifts.values()),
                exact_component_coloring_passed=True,second_stage_status=int(refined.status))
    return shifts,selected,info
