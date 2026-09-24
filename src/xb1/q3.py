"""Rebuild Q3 for attributed XB transport structures; old E4-E8 stays frozen."""
import argparse,hashlib,json,math,time
from pathlib import Path
import numpy as np
import pandas as pd
from src.q3.e8_candidates import RobustEngine
from src.q3.e6_resources import ResourceEngine,read,write_csv,write_json,ROOT,Q3,RESULTS_Q2
from src.q3.e52_geometry import SortieTrajectory
from src.q3.relay_candidate_generator import TF
from src.q3.terrain_los import blocked_line_cells
from src.q3.link_budget import fspl_db
from src.q3.e7_core import Timing,objective_key
from src.q3.e8_seed_variants import partition
from src.q3.e7_search import search
from src.q3.e7_pareto import nondominated,unique_results
import src.q3.e8_search as kernel
import src.q3.e6_export as exporter

OUT=ROOT/'results/xb1/q3'
class XBEngine(RobustEngine):
    def __init__(self,pid):
        ResourceEngine.__init__(self);self.pid=pid;self.gamma=0.;self.search_log=[]
        self.base=RESULTS_Q2/'pareto_schedules'/pid;self.dest=OUT/pid;self.dest.mkdir(parents=True,exist_ok=True)
        cache_files=[self.base/n for n in ['q2_sorties.csv','q2_box_delivery.csv','transport_trace.csv']]
        cache_files+=list((ROOT/'data/processed').glob('*.csv'))+list((ROOT/'data/processed').glob('*.json'))
        cache_files += [Path(__file__),ROOT/'src/q3/terrain_los.py',ROOT/'src/q3/e52_lazy.py',ROOT/'src/q3/e8_candidates.py']
        fingerprint={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in cache_files}
        manifest=self.dest/'cache_input_manifest.json'
        if manifest.exists():assert json.loads(manifest.read_text())==fingerprint,'XB input/code changed: create a fresh experiment and regenerate demands/pool'
        elif (self.dest/'guarded_atomic_tasks.csv').exists():
            # Migration for the initially generated, independently audited pool.
            prior=next((self.dest/'solutions').glob('*/input_manifest.json'))
            recorded=json.loads(prior.read_text())['hashes']
            for p in cache_files[:3]:assert recorded[str(p.relative_to(ROOT))]==fingerprint[str(p.relative_to(ROOT))],'Stale legacy XB pool'
        write_json(manifest,fingerprint)
        trace=read(self.base/'transport_trace.csv')
        for sid in trace.task_id.unique():
            tr=SortieTrajectory(trace,pid,sid);self.trajectories[pid,sid]=tr
            # E8 geometric helpers address P01 internally. This instance-only
            # alias points to XB trajectories; no canonical P01 artifact changes.
            self.trajectories['P01',sid]=tr
        self.access_cache.clear();self.position_cache.clear();self.edge_cache.clear()
        for p in sorted((Q3/'e8').glob('gamma_*/candidate_sites.csv'))+sorted((Q3/'e6').glob('candidate_sites_P*.csv')):
            for r in read(p).itertuples():self.add_site(r.x_m,r.y_m,r.agl_m)
        self.accepted_sites=set(self.sites)
        taskfile=self.dest/'guarded_atomic_tasks.csv'
        self.atoms=(read(taskfile) if taskfile.exists() else self.demands()).set_index('atomic_task_id',drop=False)
        edges={a:{} for a in self.atoms.index};self.edges={pid:edges,'P01':edges}
        if (self.dest/'candidate_pairs.csv').exists():
            for r in read(self.dest/'candidate_sites.csv').itertuples():self.add_site(r.x_m,r.y_m,r.agl_m)
            for r in read(self.dest/'candidate_pairs.csv').to_dict('records'):edges[r['atomic_task_id']][r['site_id']]=r

    def demands(self):
        rows=[];profile=[]
        for f in read(self.base/'q2_sorties.csv').itertuples():
            tr=self.trajectories[self.pid,f.sortie_id];cache={}
            def at(t):
                if t not in cache:
                    xyz=tr.position([t])[0];ll=TF.transform(*xyz[:2]);blocked=blocked_line_cells(self.dem,*ll,xyz[2],*self.gll)
                    cache[t]=(self.lm['transport<->G01']-fspl_db(self.pc.f_mhz,np.linalg.norm(xyz-self.gateway))-self.pc.l_obs_db*blocked,bool(blocked))
                return cache[t]
            times=tr.sample_times(f.takeoff_s,f.return_s,.5);pending=[]
            for a,b in zip(times[:-1],times[1:]):
                va=at(float(a));vb=at(float(b))
                if va[1]!=vb[1] or (va[0]>=0)!=(vb[0]>=0):pending.append((float(a),float(b)))
            while pending:
                a,b=pending.pop()
                if b-a<=.05:continue
                mid=(a+b)/2;at(mid)
                for x,y in [(a,mid),(mid,b)]:
                    vx=at(x);vy=at(y)
                    if vx[1]!=vy[1] or (vx[0]>=0)!=(vy[0]>=0):pending.append((x,y))
            ts=sorted(cache);intervals=[];begin=None
            for i,t in enumerate(ts):
                low=cache[t][0]<0
                if low and begin is None:begin=i
                if begin is not None and (not low or i==len(ts)-1):
                    a=max(f.takeoff_s,ts[max(0,begin-1)]-2);b=min(f.return_s,t+2)
                    if intervals and a<=intervals[-1][1]:intervals[-1][1]=max(b,intervals[-1][1])
                    else:intervals.append([a,b])
                    begin=None
            for i,(a,b) in enumerate(intervals):
                aid=f'{self.pid}_{f.sortie_id}_G{i:02d}'
                rows.append(dict(atomic_task_id=aid,parent_gap_id=aid,pareto_id=self.pid,transport_sortie_id=f.sortie_id,service_start_s=a,service_end_s=b,service_duration_s=b-a,Gamma_C_db=0.,construction_guard_s=2.))
            profile.extend(dict(transport_sortie_id=f.sortie_id,time_s=t,direct_margin_db=v[0],blocked=int(v[1])) for t,v in sorted(cache.items()))
            print('PROFILE',self.pid,f.sortie_id,len(intervals),flush=True)
        write_csv(self.dest/'direct_profile.csv',profile);write_csv(self.dest/'guarded_atomic_tasks.csv',rows)
        return pd.DataFrame(rows)

    def pool(self):
        if (self.dest/'candidate_pairs.csv').exists():return
        for i,sid in enumerate(sorted(self.accepted_sites)):
            self.add_edges(sid)
            if i%20==0:print('POOL',self.pid,i,len(self.accepted_sites),flush=True)
        for aid in self.atoms.index:
            if not self.common([aid]):self.search_common([aid],max_checks=1800,wanted=2)
        pairs=[r for sites in self.edges[self.pid].values() for r in sites.values()]
        used={r['site_id'] for r in pairs}
        write_csv(self.dest/'candidate_pairs.csv',pairs)
        write_csv(self.dest/'candidate_sites.csv',[{k:v for k,v in self.sites[s].items() if k!='static_energy'} for s in sorted(used)])
        write_json(self.dest/'candidate_summary.json',dict(tasks=len(self.atoms),sites=len(used),pairs=len(pairs),unresolved=[a for a in self.atoms.index if not self.common([a])],candidate_set_complete=False,searches=self.search_log))

def joint_order(e,groups,limit=60):
    # Reuse the existing joint MILP unchanged, selecting the new transport ID
    # through its Timing factory. Restored immediately; process-local adapter.
    original=kernel.Timing
    try:
        kernel.Timing=lambda engine,_legacy_pid,gs:Timing(engine,e.pid,gs)
        return kernel.relay_order_milp(e,groups,limit=limit,joint_resources=True)
    finally:kernel.Timing=original

def export(e,answer,ident):
    dest=e.dest/'solutions'/ident;dest.mkdir(parents=True,exist_ok=True);pid=e.pid
    selected=answer['selected']
    for i,r in enumerate(sorted(selected,key=lambda r:r['preparation_start_s']),1):r['relay_sortie_id']=f'{ident}_R{i:03d}'
    write_json(dest/f'selected_sorties_{pid}.json',selected);write_json(dest/f'shifts_{pid}.json',answer['shifts'])
    write_json(dest/f'plan_status_{pid}.json',dict(status='XB1_Q3_PENDING_INDEPENDENT_VALIDATION'))
    write_csv(dest/'guarded_atomic_tasks.csv',e.atoms.to_dict('records'))
    for sid in sorted({r['site_id'] for r in selected}):e.backhaul(e.sites[sid])
    write_csv(dest/f'candidate_sites_{pid}.csv',[{k:v for k,v in e.sites[s].items() if k!='static_energy'} for s in sorted({r['site_id'] for r in selected})])
    write_csv(dest/f'guarded_selected_pairs_{pid}.csv',[e.check_task(a,r['site_id']) for r in selected for a in r['task_ids']])
    old=exporter.OUT
    try:exporter.OUT=dest;exporter.export_plan(pid)
    finally:exporter.OUT=old
    for stem in ['transport_sorties','transport_uav_calendar','transport_battery_calendar']:
        p=dest/f'{stem}_{pid}.csv';df=read(p)
        for key in ['uav_id','battery_id']:
            if key in df:df[key]=df.sortie_id.map(lambda s:answer['assignments'][s][key])
        write_csv(p,df.to_dict('records'))
    metrics=json.loads((dest/f'joint_metrics_{pid}.json').read_text());metrics.update(answer['metrics'],Gamma_C_db=0.,solution_id=ident,external_structure_provenance='results/xb1/source/manifest.json',global_optimum_proven=False)
    write_json(dest/f'joint_metrics_{pid}.json',metrics);write_json(dest/'witness.json',answer)
    write_json(dest/'scenario.json',dict(Gamma_C_db=0,transport_baseline=pid))
    files=[p for p in e.base.glob('*') if p.suffix in ['.csv','.json'] and not p.name.startswith('validation')]+list((ROOT/'data/processed').glob('*.csv'))+list((ROOT/'data/processed').glob('*.json'))+[ROOT/'results/xb1/source/manifest.json']
    write_json(dest/'input_manifest.json',dict(hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}))

def run(pid):
    e=XBEngine(pid);e.pool();assert all(e.common([a]) for a in e.atoms.index)
    log=[];answers=[]
    flights=read(e.base/'q2_sorties.csv').sort_values(['preparation_start_s','sortie_id']);order=list(flights.sortie_id)
    for batch in [8,6,12]:
        groups=[]
        for start in range(0,len(order),batch):
            ids=list(e.atoms[e.atoms.transport_sortie_id.isin(order[start:start+batch])].atomic_task_id)
            if ids:groups+=partition(e,ids,'unit')
        ans,info=joint_order(e,groups);info.update(batch=batch,groups_definition=groups);log.append(info)
        write_json(e.dest/'search_log.json',log);print('SEARCH',pid,batch,info,flush=True)
        if ans:answers.append(ans);break
    if not answers:
        write_json(e.dest/'status.json',dict(status='XB1_Q3_NO_WITNESS_IN_BOUNDED_SEARCH',physical_infeasibility_proven=False));return
    seed=answers[0]
    for objective in ['timeliness','makespan','energy']:
        best,archive,info=search(e,seed,objective=objective,rounds=1,repairs_per_round=8,label=pid+'_'+objective)
        answers+=archive;write_json(e.dest/f'{objective}_search.json',info)
        if best and objective=='timeliness':seed=best
    points=nondominated(unique_results(answers));write_json(e.dest/'frontier_witnesses.json',points)
    for i,ans in enumerate(points,1):export(e,ans,f'{pid}_Q3_{i:03d}')
    write_json(e.dest/'status.json',dict(status='XB1_Q3_INDEPENDENT_VALIDATION_REQUIRED',solutions=len(points)))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('pid');a=p.parse_args();run(a.pid)
