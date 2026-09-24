"""E6 conflict-driven relay expansion and fixed-transport resource scheduling."""
from __future__ import annotations

from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import time

import numpy as np
import pandas as pd
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import coo_matrix

from src.common.paths import PROCESSED_DIR, RESULTS_Q2, RESULTS_DIR
from src.common.terrain import Dem
from src.common.charging import charge_time_s
from src.q3.e52_lazy import Engine, write_csv, write_json
from src.q3.e52_geometry import SortieTrajectory, safe_bbox
from src.q3.link_budget import load_comm_params, pair_lmax, max_range_m
from src.q3.relay_candidate_generator import TF
from src.q3.relay_geometry import load_relay_params, o01_pos

ROOT=Path(__file__).resolve().parents[2]
Q3=RESULTS_DIR/'q3'
OUT=Q3/'e6'
CONFIG=dict(seed=20260924,workers=1,communication_concurrency='MULTI_TRANSPORT_SINGLE_SITE',
            comm_power_per_active_module=True,gamma_c_db=0,expansion_time_budget_s=180,
            expansion_grid_m=120,expansion_heights_m=[300,250,200],
            candidate_set_complete=False,transport_changes='NONE_UNLESS_LEVEL_C',
            milp_time_limit_s=90,mip_rel_gap=1e-6)


def read(path):return pd.read_csv(path,float_precision='round_trip')


class ResourceEngine(Engine):
    """Reuse frozen E52 numerical primitives; initialize ONLY from E52 authority.

    Do not call the old Engine constructor: that loads legacy warm-start tables.
    """
    def __init__(self):
        self.dem=Dem();self.pc,_=load_comm_params()
        self.pr,self.lm=load_relay_params(),pair_lmax()
        self.origin=np.array(o01_pos())
        raw=json.loads((PROCESSED_DIR/'communication_parameters.json').read_text())
        hg=float(raw['endpoints']['固定网关 G01']['天线离地高度（m）']['value'])
        self.gateway=self.origin+[0,0,hg]
        self.gll=(*TF.transform(*self.gateway[:2]),self.gateway[2])
        self.dtr=max_range_m(self.lm['transport<->relay'],self.pc,False)
        self.drg=max_range_m(self.lm['relay<->G01'],self.pc,False)
        self.sites={};self.access_cache={};self.position_cache={};self.stats=Counter()
        self.trajectories={};self.edge_cache={}
        for pid in ['P01','P02','P03']:
            frame=read(RESULTS_Q2/'pareto_schedules'/pid/'transport_trace.csv')
            for sid in frame.task_id.unique():
                self.trajectories[pid,sid]=SortieTrajectory(frame,pid,sid)
        for row in read(Q3/'relay_sites_e52.csv').to_dict('records'):
            s=self.add_site(row['x_m'],row['y_m'],row['agl_m'])
            assert s['site_id']==row['site_id'],(s['site_id'],row['site_id'])
        self.atoms=read(Q3/'relay_atomic_tasks_e52.csv').set_index('atomic_task_id',drop=False)
        self.original=read(Q3/'relay_task_candidates_e52.csv')
        self.edges={pid:{} for pid in ['P01','P02','P03']}
        for row in self.original.to_dict('records'):
            self.edges[row['pareto_id']].setdefault(row['atomic_task_id'],{})[row['site_id']]=row

    def check_task(self,aid,sid):
        key=(aid,sid)
        if key in self.edge_cache:return self.edge_cache[key]
        t=self.atoms.loc[aid];tr=self.trajectories[t.pareto_id,t.transport_sortie_id]
        rec=self.check(tr,sid,float(t.service_start_s),float(t.service_end_s))
        if rec:
            rec.update(atomic_task_id=aid,parent_gap_id=t.parent_gap_id,pareto_id=t.pareto_id,
                       transport_sortie_id=t.transport_sortie_id,service_start_s=float(t.service_start_s),
                       service_end_s=float(t.service_end_s),service_duration_s=float(t.service_duration_s))
        self.edge_cache[key]=rec
        return rec


def min_site_cover(active,edges):
    if not active:return 0,[]
    bits={aid:1<<i for i,aid in enumerate(active)}
    masks={}
    for aid in active:
        for sid in edges[aid]:masks[sid]=masks.get(sid,0)|bits[aid]
    dp={0:[]}
    for sid,mask in sorted(masks.items()):
        for old,used in list(dp.items()):
            new=old|mask
            if new not in dp or len(used)+1<len(dp[new]):dp[new]=used+[sid]
    target=(1<<len(active))-1
    return (len(dp[target]),dp[target]) if target in dp else (None,[])


def diagnose(engine,pid):
    atoms=engine.atoms[engine.atoms.pareto_id==pid]
    times=sorted(set(atoms.service_start_s)|set(atoms.service_end_s))
    events=[]
    for a,b in zip(times[:-1],times[1:]):
        rows=atoms[(atoms.service_start_s<(a+b)/2)&(atoms.service_end_s>(a+b)/2)]
        ids=list(rows.atomic_task_id)
        number,witness=min_site_cover(ids,engine.edges[pid])
        events.append(dict(start_s=float(a),end_s=float(b),active_tasks=ids,
                           active_task_count=len(ids),minimum_current_pool_sites=number,
                           witness_sites=witness,singleton_tasks=[x for x in ids if len(engine.edges[pid][x])==1]))
    maxsite=max(e['minimum_current_pool_sites'] for e in events)
    shared={}
    for aid,sites in engine.edges[pid].items():
        for sid in sites:shared.setdefault(sid,[]).append(aid)
    return dict(pareto_id=pid,peak_active_tasks=max(e['active_task_count'] for e in events),
                peak_minimum_sites=maxsite,events=events,
                first_peak=next(e for e in events if e['minimum_current_pool_sites']==maxsite),
                shared_sites={s:aa for s,aa in shared.items() if len(aa)>1},
                interpretation='CURRENT_POOL_INFEASIBLE' if maxsite>2 else 'INSTANTANEOUS_COVER_BOUND_AT_MOST_TWO_NOT_A_SCHEDULE')


def expand(engine,pid,before):
    """Search only joint regions derived from observed >2-site conflict sets."""
    started=time.monotonic();attempts=[]
    conflicts=sorted([e for e in before['events'] if e['minimum_current_pool_sites']>2],
                     key=lambda e:(-e['minimum_current_pool_sites'],e['start_s']))
    seeds=sorted({sid for pool in engine.edges.values() for sites in pool.values() for sid in sites})
    seen_groups=set()
    # Whole-task validity is tested, not just validity inside the event overlap.
    relevant=sorted(set(a for event in conflicts for a in event['active_tasks']))
    def consider(sid,origin,target):
        covered=[]
        for aid in relevant:
            task=engine.atoms.loc[aid]
            tr=engine.trajectories[pid,task.transport_sortie_id]
            if not engine.cheap(tr,[sid],task.service_start_s,task.service_end_s):continue
            rec=engine.check_task(aid,sid)
            if rec:
                engine.edges[pid][aid][sid]=rec;covered.append(aid)
        return covered
    # Cross-validate the existing authoritative site library for genuine conflicts.
    for i,sid in enumerate(seeds):
        consider(sid,'E52_SITE_CROSS_VALIDATION',relevant)
        if (i+1)%20==0:print(f'{pid} cross-validated {i+1}/{len(seeds)} sites',flush=True)
    after_library=diagnose(engine,pid)
    attempts.append(dict(method='E52_SITE_CROSS_VALIDATION',sites_examined=len(seeds),
                         before_peak=before['peak_minimum_sites'],after_peak=after_library['peak_minimum_sites'],
                         elapsed_s=time.monotonic()-started))
    # Candidate demand is deduplicated between repeated event intervals.
    for event in conflicts:
        active=event['active_tasks']
        if min_site_cover(active,engine.edges[pid])[0]<=2:continue
        centers=[]
        for aid in active:
            t=engine.atoms.loc[aid];tr=engine.trajectories[pid,t.transport_sortie_id]
            centers.append(tr.position(tr.vertices(t.service_start_s,t.service_end_s)).mean(axis=0))
        centers=np.array(centers)
        # Data-driven two-cluster hypotheses; search full group and complementary
        # sides of every centroid-direction cut (small observed conflict sets).
        # A complementary group to an existing site directly targets a 2-site
        # cover; searching all 7 tasks at one site first wastes the budget.
        complement=[]
        for sid in seeds:
            remaining=[aid for aid in active if sid not in engine.edges[pid][aid]]
            if 1<len(remaining)<len(active):complement.append(remaining)
        groups=sorted(complement,key=lambda g:len(g))
        spatial_groups=[active]
        for axis in [0,1]:
            order=np.argsort(centers[:,axis],kind='stable')
            for split in range(1,len(active)):
                spatial_groups.extend([[active[i] for i in order[:split]],[active[i] for i in order[split:]]])
        groups+=sorted(spatial_groups,key=lambda g:abs(len(g)-len(active)/2))
        for group in groups:
            group=tuple(sorted(group))
            if len(group)<2 or group in seen_groups:continue
            seen_groups.add(group)
            if set.intersection(*(set(engine.edges[pid][aid]) for aid in group)):continue
            pts=[]
            for aid in group:
                t=engine.atoms.loc[aid];tr=engine.trajectories[pid,t.transport_sortie_id]
                pts.extend(tr.position(tr.vertices(t.service_start_s,t.service_end_s)))
            pts=np.array(pts);bbox=safe_bbox(pts,engine.dtr,engine.drg,engine.gateway)
            if bbox is None:
                attempts.append(dict(group=list(group),result='EMPTY_NECESSARY_REGION'));continue
            x0,x1,y0,y1=bbox;step=CONFIG['expansion_grid_m']
            x,y=np.meshgrid(np.arange(math.ceil(x0/step),math.floor(x1/step)+1)*step,
                            np.arange(math.ceil(y0/step),math.floor(y1/step)+1)*step)
            xy=np.c_[x.ravel(),y.ravel()]
            # Prefer nearby high terrain: terrain affects LOS, but is not used
            # as an exclusion or a claim that the candidate pool is complete.
            center=pts.mean(axis=0)
            xy=xy[np.argsort(np.sum((xy-center[:2])**2,axis=1),kind='stable')]
            examined=0;found=None;tick=time.monotonic()
            for px,py in xy:
                if time.monotonic()-started>CONFIG['expansion_time_budget_s']:break
                if time.monotonic()-tick>8:break
                for agl in CONFIG['expansion_heights_m']:
                    site=engine.add_site(float(px),float(py),float(agl))
                    if site is None:continue
                    sid=site['site_id'];examined+=1
                    # Cheap vectorized group-distance gate before any LOS.
                    xyz=np.array([site[k] for k in ['x_m','y_m','z_amsl_m']])
                    if np.linalg.norm(pts-xyz,axis=1).max()>engine.dtr:continue
                    if engine.backhaul(site)<0:continue
                    if all(engine.check_task(aid,sid) is not None for aid in group):
                        found=sid;covered=consider(sid,'TARGETED_GROUP_GRID',group);break
                if found:break
            attempts.append(dict(conflict_interval=[event['start_s'],event['end_s']],group=list(group),
                                 bbox=bbox,examined=examined,runtime_s=time.monotonic()-tick,
                                 result='COMMON_SITE_FOUND' if found else 'NOT_FOUND_UNDER_SEARCH_BUDGET',
                                 site_id=found,covered_tasks=covered if found else [],
                                 minimum_sites_after=min_site_cover(active,engine.edges[pid])[0]))
            print(f'expansion {pid} group={len(group)} n={examined} found={found} active_cover={min_site_cover(active,engine.edges[pid])[0]}',flush=True)
            if min_site_cover(active,engine.edges[pid])[0]<=2:break
        if time.monotonic()-started>CONFIG['expansion_time_budget_s']:break
    return dict(before=before,after=diagnose(engine,pid),attempts=attempts,runtime_s=time.monotonic()-started)


def interval_union(windows):
    merged=[]
    for a,b in sorted(windows):
        if merged and a<=merged[-1][1]+1e-9:merged[-1][1]=max(b,merged[-1][1])
        else:merged.append([float(a),float(b)])
    return merged


def resource_footprint_diagnosis(engine,pid):
    """Necessary UAV-occupancy cores, including travel/preparation/turnaround.

    For each task, intersection of ALL candidate-specific UAV occupancy
    intervals is unavoidable. Distinct fixed sites cannot share one UAV while
    these cores overlap. Same-site merging may share occupancy and is allowed.
    """
    cores=[]
    for aid,sites in engine.edges[pid].items():
        rows=[sortie_column(engine,pid,sid,[aid]) for sid in sites]
        rows=[r for r in rows if r is not None]
        if not rows:continue
        a=max(r['preparation_start_s'] for r in rows)
        b=min(r['uav_available_s'] for r in rows)
        if b>a:cores.append((aid,a,b))
    endpoints=sorted({v for _,a,b in cores for v in [a,b]});events=[]
    for a,b in zip(endpoints[:-1],endpoints[1:]):
        active=[aid for aid,lo,hi in cores if lo<(a+b)/2<hi]
        if not active:continue
        number,witness=min_site_cover(active,engine.edges[pid])
        events.append(dict(start_s=a,end_s=b,active_tasks=active,minimum_current_pool_sites=number,witness_sites=witness))
    peak=max(e['minimum_current_pool_sites'] for e in events)
    return dict(peak_unavoidable_uav_bound=peak,events=events,
                first_peak=next(e for e in events if e['minimum_current_pool_sites']==peak),
                interpretation='CANDIDATE_POOL_RESOURCE_LOWER_BOUND_NOT_PHYSICAL_INFEASIBILITY')


def expand_resource_conflicts(engine,pid):
    before=resource_footprint_diagnosis(engine,pid);tick=time.monotonic()
    relevant=sorted({aid for e in before['events'] if e['minimum_current_pool_sites']>2 for aid in e['active_tasks']})
    sites=sorted({sid for sites in engine.edges[pid].values() for sid in sites})
    added=[]
    for i,sid in enumerate(sites):
        for aid in relevant:
            if sid in engine.edges[pid][aid]:continue
            t=engine.atoms.loc[aid];tr=engine.trajectories[pid,t.transport_sortie_id]
            if not engine.cheap(tr,[sid],t.service_start_s,t.service_end_s):continue
            rec=engine.check_task(aid,sid)
            if rec:
                engine.edges[pid][aid][sid]=rec;added.append(dict(atomic_task_id=aid,site_id=sid))
        if (i+1)%20==0:print(f'{pid} resource-conflict cross-check {i+1}/{len(sites)} added={len(added)}',flush=True)
    after=resource_footprint_diagnosis(engine,pid)
    return dict(before=before,after=after,target_tasks=relevant,existing_sites_examined=len(sites),
                added_pairs=added,runtime_s=time.monotonic()-tick,
                reason='Communication-event conflicts alone miss overlapping flight/turnaround footprints and multiple short-separated gaps on the same sortie.')


def sortie_column(engine,pid,sid,task_ids,shifts=None):
    shifts=shifts or {}
    windows=[]
    for aid in task_ids:
        t=engine.atoms.loc[aid];delta=shifts.get(t.transport_sortie_id,0.)
        windows.append((float(t.service_start_s+delta),float(t.service_end_s+delta)))
    union=interval_union(windows);start=union[0][0];end=union[-1][1]
    active=sum(b-a for a,b in union);idle=end-start-active
    site=engine.sites[sid];en=engine.energy(site,0);p=engine.pr
    service_energy=(p['hover_power_kw']+p['comm_power_kw'])*active/3600
    idle_energy=p['hover_power_kw']*idle/3600
    energy=en['flight_energy_kwh']+en['setup_energy_kwh']+service_energy+idle_energy
    if energy>(1-p['rho'])*p['energy_kwh']+1e-9:return None
    takeoff=start-p['setup_time_s']-en['outbound_time_s'];prep=takeoff-p['prep_time_s']
    if prep< -1e-7:return None
    ret=end+en['return_time_s'];soc=1-energy/p['energy_kwh']
    full=float(read(PROCESSED_DIR/'relay_energy_components.csv').iloc[0].full_charge_time_s)
    charge=charge_time_s(soc,full)
    return dict(site_id=sid,task_ids=sorted(task_ids),preparation_start_s=max(0.,prep),takeoff_s=takeoff,
                arrival_s=start-p['setup_time_s'],setup_start_s=start-p['setup_time_s'],service_start_s=start,
                service_end_s=end,return_s=ret,uav_available_s=ret+p['turnaround_time_s'],
                energy_ready_s=ret+charge,charge_duration_s=charge,return_soc=soc,
                outbound_time_s=en['outbound_time_s'],return_time_s=en['return_time_s'],
                flight_energy_kwh=en['flight_energy_kwh'],setup_energy_kwh=en['setup_energy_kwh'],
                active_communication_s=active,idle_hover_s=idle,active_energy_kwh=service_energy,
                idle_energy_kwh=idle_energy,total_energy_kwh=energy,
                energy_margin_kwh=(1-p['rho'])*p['energy_kwh']-energy,service_windows=union)


def columns(engine,pid,shifts=None):
    """Finite full-window columns; each covers all eligible tasks inside its span.

    Incomplete column pool: infeasibility here is not physical infeasibility.
    """
    shifts=shifts or {};by_site={}
    for aid,sites in engine.edges[pid].items():
        for sid in sites:by_site.setdefault(sid,[]).append(aid)
    found={}
    for sid,ids in by_site.items():
        starts={a:float(engine.atoms.loc[a].service_start_s)+shifts.get(engine.atoms.loc[a].transport_sortie_id,0.) for a in ids}
        ends={a:float(engine.atoms.loc[a].service_end_s)+shifts.get(engine.atoms.loc[a].transport_sortie_id,0.) for a in ids}
        subsets={tuple([a]) for a in ids}
        for a in sorted(set(starts.values())):
            for b in sorted(set(ends.values())):
                if b<a:continue
                subset=tuple(sorted(t for t in ids if starts[t]>=a-1e-7 and ends[t]<=b+1e-7))
                if subset:subsets.add(subset)
        for subset in sorted(subsets):
            col=sortie_column(engine,pid,sid,subset,shifts)
            if col:found[sid,subset]=col
    return list(found.values())


def solve_columns(cols,task_ids,time_limit=90,relay_capacity=2,objective_kind='energy',energy_capacity=6):
    """Set partition + exact interval-graph capacities for identical resources."""
    n=len(cols);ids={a:i for i,a in enumerate(task_ids)}
    # Allow columns to overlap in potential task coverage, then select exactly
    # one provider per task and tighten each sortie. Forcing equality before
    # this step can create artificial infeasibility with full-window columns.
    rr=[];cc=[];vv=[];lower=[1.]*len(ids);upper=[np.inf]*len(ids)
    for j,col in enumerate(cols):
        for aid in col['task_ids']:rr.append(ids[aid]);cc.append(j);vv.append(1.)
    for start,end,cap in [('preparation_start_s','uav_available_s',relay_capacity),('takeoff_s','energy_ready_s',energy_capacity)]:
        # Capacity can increase only at a column start. Half-open occupancy.
        times=np.unique([col[start] for col in cols]);offset=len(lower)
        lower.extend([-np.inf]*len(times));upper.extend([float(cap)]*len(times))
        for j,col in enumerate(cols):
            first=np.searchsorted(times,col[start]-1e-8)
            last=np.searchsorted(times,col[end]-1e-8)
            count=last-first
            rr.extend(range(offset+first,offset+last));cc.extend([j]*count);vv.extend([1.]*count)
    matrix=coo_matrix((vv,(rr,cc)),shape=(len(lower),n)).tocsc()
    objective=np.array([c['total_energy_kwh'] if objective_kind=='energy' else 1. for c in cols])
    started=time.monotonic()
    result=milp(objective,integrality=np.ones(n),bounds=Bounds(np.zeros(n),np.ones(n)),
                constraints=LinearConstraint(matrix,np.array(lower),np.array(upper)),
                options=dict(time_limit=time_limit,mip_rel_gap=CONFIG['mip_rel_gap']))
    selected=[] if result.x is None else [cols[i] for i in np.flatnonzero(result.x>0.5)]
    info=dict(status=int(result.status),message=str(result.message),columns=n,constraints=len(lower),
              runtime_s=time.monotonic()-started,objective_energy_kwh=None if result.fun is None else float(result.fun),
              mip_gap=None if getattr(result,'mip_gap',None) is None else float(result.mip_gap),
              dual_bound=None if getattr(result,'mip_dual_bound',None) is None else float(result.mip_dual_bound),
              relay_capacity=relay_capacity,energy_capacity=energy_capacity,objective_kind=objective_kind,
              optimality_scope='FINITE_GENERATED_SORTIE_COLUMN_POOL_ONLY')
    return selected,info


def unique_assignment(engine,pid,selected,shifts=None):
    pending=set(engine.edges[pid]);out=[]
    for row in sorted(selected,key=lambda r:(-len(r['task_ids']),r['total_energy_kwh'],r['site_id'])):
        tasks=sorted(pending.intersection(row['task_ids']))
        if not tasks:continue
        tightened=sortie_column(engine,pid,row['site_id'],tasks,shifts)
        assert tightened is not None
        assert tightened['preparation_start_s']>=row['preparation_start_s']-1e-6
        assert tightened['uav_available_s']<=row['uav_available_s']+1e-6
        assert tightened['energy_ready_s']<=row['energy_ready_s']+1e-6
        out.append(tightened);pending.difference_update(tasks)
    assert not pending
    return out


def color_intervals(rows,start,end,resource_ids,key):
    ready={name:0. for name in resource_ids}
    for row in sorted(rows,key=lambda r:(r[start],r[end])):
        options=[name for name in resource_ids if ready[name]<=row[start]+1e-6]
        if not options:raise ValueError(f'Cannot color {key}')
        name=min(options,key=lambda x:(ready[x],x));row[key]=name;ready[name]=row[end]


def save_pool(engine,pid):
    pairs=[row for aid,sites in engine.edges[pid].items() for row in sites.values()]
    used={r['site_id'] for r in pairs}
    write_csv(OUT/f'candidate_pairs_{pid}.csv',pairs)
    write_csv(OUT/f'candidate_sites_{pid}.csv',[{k:v for k,v in engine.sites[sid].items() if k!='static_energy'} for sid in sorted(used)])



if __name__=='__main__':
    raise SystemExit('Use python -m src.q3.e6_run for search or src.q3.e6_replay for the committed witness.')
