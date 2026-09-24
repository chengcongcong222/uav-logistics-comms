#!/usr/bin/env python3
"""Independent E52 artifact audit; no imports from E52 generation/sampling code.

Uses the frozen authoritative DEM LOS primitive, but reconstructs trajectories,
sampling, propagation, interval refinement and energy from primary inputs.
Checks ALL retained pairs. This is a numerical certificate, not an analytic
proof that no sub-grid discontinuity exists between observation times.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import sys
import time

import numpy as np
import pandas as pd
from pyproj import Transformer

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.common.terrain import Dem
from src.q3.link_budget import load_comm_params, pair_lmax
from src.q3.relay_geometry import load_relay_params
from src.q3.terrain_los import blocked_line_cells

Q3 = ROOT / 'results/q3'


def require(condition, message):
    if not condition:
        raise ValueError(message)


class IndependentAudit:
    def __init__(self):
        self.dem=Dem()
        self.radio,_=load_comm_params()
        self.budgets=pair_lmax()
        self.params=load_relay_params()
        self.tf=Transformer.from_crs(32649,4326,always_xy=True)
        node=pd.read_csv(ROOT/'data/processed/nodes.csv').set_index('node_id').loc['O01']
        raw=json.loads((ROOT/'data/processed/communication_parameters.json').read_text())
        hg=raw['endpoints']['固定网关 G01']['天线离地高度（m）']['value']
        self.origin=np.array([node.x_m,node.y_m,node.ground_elevation_m],float)
        self.gateway=self.origin+np.array([0,0,hg])
        self.gateway_ll=(*self.tf.transform(*self.gateway[:2]),self.gateway[2])
        self.traces={}
        self.samples=0
        self.refinements=0
        for pid in ['P01','P02','P03']:
            frame=pd.read_csv(ROOT/f'results/q2/pareto_schedules/{pid}/transport_trace.csv')
            for sid,rows in frame.groupby('task_id'):
                require(not (rows.groupby('time')[['x','y','z']].nunique()>1).any().any(),f'Conflicting trace {pid}/{sid}')
                rows=rows.sort_values('time').drop_duplicates('time')
                self.traces[pid,sid]=(rows.time.to_numpy(float),rows[['x','y','z']].to_numpy(float))

    def position(self,key,t):
        times,xyz=self.traces[key]
        require(times[0]-1e-8<=t<=times[-1]+1e-8,'Trace extrapolation')
        i=min(max(int(np.searchsorted(times,t,side='right'))-1,0),len(times)-2)
        weight=(t-times[i])/(times[i+1]-times[i])
        return xyz[i]+weight*(xyz[i+1]-xyz[i])

    def link(self,xyz,site):
        ll=self.tf.transform(*xyz[:2])
        blocked=blocked_line_cells(self.dem,*ll,xyz[2],site.lon,site.lat,site.z_amsl_m)
        distance=float(np.linalg.norm(xyz-[site.x_m,site.y_m,site.z_amsl_m]))
        loss=32.45+20*math.log10(self.radio.f_mhz)+20*math.log10(max(distance,1e-6)/1000)
        self.samples+=1
        return self.budgets['transport<->relay']-loss-self.radio.l_obs_db*blocked,bool(blocked)

    def interval(self,key,site,a,b,step=0.5,fail_early=False):
        trace_times,_=self.traces[key]
        ts={float(a),float(b)}
        ts.update(float(t) for t in trace_times if a<t<b)
        ts.update(k*step for k in range(math.ceil(a/step),math.floor(b/step)+1))
        ordered=sorted(ts)
        require(max(np.diff(ordered))<=step+1e-8,'Sampling time gap')
        minimum=float('inf')
        prior=None
        pending=[]
        for t in ordered:
            xyz=self.position(key,t)
            value=self.link(xyz,site)
            minimum=min(minimum,value[0])
            if fail_early and minimum<0:
                return minimum
            if prior is not None:
                require(np.linalg.norm(xyz[:2]-prior[2][:2])<=7.5+1e-6,'Sampling displacement > 7.5m')
                if value[1]!=prior[1][1] or (value[0]>=0)!=(prior[1][0]>=0):
                    pending.append((prior[0],prior[1],t,value))
            prior=(t,value,xyz)
        while pending:
            a0,v0,b0,v1=pending.pop()
            if b0-a0<=0.1:
                continue
            mid=(a0+b0)/2
            value=self.link(self.position(key,mid),site)
            self.refinements+=1
            minimum=min(minimum,value[0])
            if fail_early and minimum<0:
                return minimum
            if value[1]!=v0[1] or (value[0]>=0)!=(v0[0]>=0):
                pending.append((a0,v0,mid,value))
            if value[1]!=v1[1] or (value[0]>=0)!=(v1[0]>=0):
                pending.append((mid,value,b0,v1))
        return minimum

    def backhaul(self,site):
        blocked=blocked_line_cells(self.dem,site.lon,site.lat,site.z_amsl_m,*self.gateway_ll)
        distance=float(np.linalg.norm(np.array([site.x_m,site.y_m,site.z_amsl_m])-self.gateway))
        loss=32.45+20*math.log10(self.radio.f_mhz)+20*math.log10(max(distance,1e-6)/1000)
        return self.budgets['relay<->G01']-loss-self.radio.l_obs_db*blocked

    def energy(self,site,duration):
        # Independent arithmetic and terrain sampling, not stored energy fields.
        p=self.params
        lon0,lat0=self.tf.transform(*self.origin[:2])
        d=math.hypot(site.x_m-self.origin[0],site.y_m-self.origin[1])
        n=max(2,int(d/30)+1)
        heights=[]
        for u in np.arange(n+1)/n:
            heights.append(self.dem.sample(lon0+u*(site.lon-lon0),lat0+u*(site.lat-lat0)))
            heights.append(self.dem.sample(site.lon+u*(lon0-site.lon),site.lat+u*(lat0-site.lat)))
        cruise=max(max(heights)+50,float(self.origin[2]),site.z_amsl_m)
        up_out=cruise-self.origin[2]; up_back=cruise-site.z_amsl_m
        flight=2*p['cruise_power_kw']*d/p['cruise_speed_mps']/3600
        flight+=p['takeoff_mass_kg']*9.80665*(up_out+up_back)/(p['climb_eff']*3.6e6)
        require(p['descend_eff']==0,'Undefined nonzero descent rule')
        setup=(p['hover_power_kw']+p['comm_power_kw'])*p['setup_time_s']/3600
        service=(p['hover_power_kw']+p['comm_power_kw'])*duration/3600
        total=flight+setup+service
        outbound=up_out/p['max_climb_mps']+d/p['cruise_speed_mps']+up_back/p['max_descend_mps']
        back=up_back/p['max_climb_mps']+d/p['cruise_speed_mps']+up_out/p['max_descend_mps']
        return dict(flight_energy_kwh=flight,setup_energy_kwh=setup,service_energy_kwh=service,
                    total_energy_kwh=total,energy_margin_kwh=(1-p['rho'])*p['energy_kwh']-total,
                    return_soc=1-total/p['energy_kwh'],outbound_time_s=outbound,return_time_s=back)


def audit():
    start=time.monotonic()
    meta=json.loads((Q3/'e52_run_meta.json').read_text())
    for file,expected in meta['input_hashes'].items():
        require(hashlib.sha256((ROOT/file).read_bytes()).hexdigest()==expected,f'Stale run: {file}')
    require(meta['config']['candidate_set_complete'] is False,'Wrong completeness claim')
    atoms=pd.read_csv(Q3/'relay_atomic_tasks_e52.csv')
    pairs=pd.read_csv(Q3/'relay_task_candidates_e52.csv')
    sites=pd.read_csv(Q3/'relay_sites_e52.csv').set_index('site_id')
    unresolved=pd.read_csv(Q3/'relay_unresolved_e52.csv')
    require(len(unresolved)==0,'Unresolved intervals remain')
    require(len(atoms)>0 and len(pairs)>0,'Empty solution')
    require(atoms.atomic_task_id.is_unique and sites.index.is_unique,'Duplicate identities')
    require(not pairs.duplicated(['atomic_task_id','site_id']).any(),'Duplicate pair')
    require(set(pairs.atomic_task_id)==set(atoms.atomic_task_id),'Candidate/task mismatch')
    require(set(pairs.site_id)==set(sites.index),'Candidate/site mismatch')
    checker=IndependentAudit()
    site_checks=[]
    for sid,s in sites.iterrows():
        lon,lat=checker.tf.transform(s.x_m,s.y_m)
        ground=checker.dem.sample(lon,lat)
        require(abs(lon-s.lon)<1e-10 and abs(lat-s.lat)<1e-10,f'Coordinate mismatch {sid}')
        require(abs(ground-s.ground_elevation_m)<1e-8 and abs(ground+s.agl_m-s.z_amsl_m)<1e-8,f'AGL mismatch {sid}')
        require(0<s.agl_m<=checker.params['max_agl_m'],f'Illegal height {sid}')
        margin=checker.backhaul(s)
        require(margin>=0 and abs(margin-s.backhaul_margin_db)<1e-7,f'Backhaul mismatch {sid}')
        site_checks.append(dict(site_id=sid,backhaul_margin_db=margin))
    records=[]
    amap=atoms.set_index('atomic_task_id')
    for i,row in enumerate(pairs.itertuples(),1):
        atom=amap.loc[row.atomic_task_id]
        for field in ['pareto_id','parent_gap_id','transport_sortie_id','service_start_s','service_end_s','service_duration_s']:
            require(getattr(row,field)==atom[field],f'Pair/task mismatch {row.atomic_task_id}/{field}')
        s=sites.loc[row.site_id]
        key=(row.pareto_id,row.transport_sortie_id)
        minimum=checker.interval(key,s,row.service_start_s,row.service_end_s)
        require(minimum>=0,f'Access outage {row.atomic_task_id}/{row.site_id}: {minimum}')
        rg=checker.backhaul(s)
        require(abs(minimum-row.min_access_margin_db)<1e-7,f'Stored access minimum mismatch {row.atomic_task_id}')
        require(abs(rg-row.backhaul_margin_db)<1e-7,f'Stored backhaul mismatch {row.atomic_task_id}')
        require(abs(min(minimum,rg)-row.min_twohop_margin_db)<1e-7,f'Stored twohop mismatch {row.atomic_task_id}')
        en=checker.energy(s,row.service_end_s-row.service_start_s)
        for field,value in en.items():
            require(abs(value-getattr(row,field))<1e-6,f'Energy/time mismatch {row.atomic_task_id}/{field}')
        require(en['energy_margin_kwh']>=0,'Energy infeasible')
        ready=checker.params['prep_time_s']+checker.params['setup_time_s']+en['outbound_time_s']
        require(abs(ready-row.earliest_ready_s)<1e-6,'Ready time mismatch')
        require(abs(max(0,ready-row.service_start_s)-row.required_transport_shift_s)<1e-6,'Shift mismatch')
        records.append(dict(atomic_task_id=row.atomic_task_id,site_id=row.site_id,
                            independent_min_access_margin_db=minimum,independent_backhaul_margin_db=rg,
                            independent_total_energy_kwh=en['total_energy_kwh'],
                            independent_energy_margin_kwh=en['energy_margin_kwh']))
        if i%10==0:
            print(f'Independent pairs {i}/{len(pairs)} checked',flush=True)
    print('E52_RELAY_CANDIDATES_VALID',flush=True)
    print('E52_RELAY_ENERGY_VALID',flush=True)
    expected_parents=set()
    merge_checks=0
    for pid in ['P01','P02','P03']:
        gaps=pd.read_csv(Q3/f'direct_gaps_{pid}.csv')
        for gi,gap in enumerate(gaps.itertuples()):
            parent=f'{pid}_G{gi:03d}';expected_parents.add(parent)
            group=atoms[atoms.parent_gap_id==parent].sort_values('service_start_s')
            require(len(group)>0,f'Missing parent {parent}')
            cursor=gap.start_s
            for atom in group.itertuples():
                require(atom.pareto_id==pid and atom.transport_sortie_id==gap.sortie_id,'Wrong trajectory identity')
                require(abs(atom.service_start_s-cursor)<1e-6,f'Hole/overlap {parent}')
                require(atom.service_end_s>atom.service_start_s,'Nonpositive interval')
                require(abs(atom.service_duration_s-(atom.service_end_s-atom.service_start_s))<1e-7,'Duration mismatch')
                require(atom.candidate_count==int((pairs.atomic_task_id==atom.atomic_task_id).sum())>=1,'No candidates/count mismatch')
                cursor=atom.service_end_s
            require(abs(cursor-gap.end_s)<1e-6,f'Incomplete parent {parent}')
            rr=list(group.itertuples())
            for left,right in zip(rr[:-1],rr[1:]):
                ids=pairs[pairs.atomic_task_id.isin([left.atomic_task_id,right.atomic_task_id])].site_id.unique()
                for sid in ids:
                    s=sites.loc[sid];merge_checks+=1
                    en=checker.energy(s,right.service_end_s-left.service_start_s)
                    if en['energy_margin_kwh']<0:
                        continue
                    m=checker.interval((pid,gap.sortie_id),s,left.service_start_s,right.service_end_s,fail_early=True)
                    require(m<0,f'Merge-back missed feasible union {left.atomic_task_id}/{right.atomic_task_id}')
    require(set(atoms.parent_gap_id)==expected_parents,'Extraneous/missing parent')
    print('E52_ATOMIC_TASKS_VALID',flush=True)
    outputs=['relay_atomic_tasks_e52.csv','relay_task_candidates_e52.csv','relay_sites_e52.csv','relay_unresolved_e52.csv']
    report=dict(gate='E5_Q3_RELAY_TASKS_READY',candidates='E52_RELAY_CANDIDATES_VALID',
                energy='E52_RELAY_ENERGY_VALID',atomic_tasks='E52_ATOMIC_TASKS_VALID',
                fingerprint=meta['fingerprint'],parent_gaps=len(expected_parents),atomic_task_count=len(atoms),
                all_candidate_pairs_checked=len(pairs),sites_checked=len(sites),unresolved=0,
                access_samples=checker.samples,boundary_refinement_samples=checker.refinements,
                adjacent_union_checks=merge_checks,runtime_s=time.monotonic()-start,
                output_sha256={f:hashlib.sha256((Q3/f).read_bytes()).hexdigest() for f in outputs},
                limitations=['Candidate set incomplete; no relay resource scheduling yet.',
                            'Numerical 0.5s plus phase/boundary/refinement validation, not analytic continuous-time proof.',
                            'Frozen primary DEM LOS semantics reused; independent path sampling is a separate sensitivity question.'])
    out=Q3/'e52_rescue'
    pd.DataFrame(records).to_csv(out/'independent_candidate_audit.csv',index=False)
    pd.DataFrame(site_checks).to_csv(out/'independent_site_audit.csv',index=False)
    (out/'validation.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2),flush=True)


if __name__=='__main__':
    try:
        audit()
    except Exception as exc:
        out=Q3/'e52_rescue'
        out.mkdir(parents=True,exist_ok=True)
        (out/'validation.json').write_text(json.dumps(dict(gate='E5_Q3_RELAY_TASKS_BLOCKED',error=str(exc)),indent=2)+'\n')
        raise
