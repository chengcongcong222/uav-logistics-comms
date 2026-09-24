"""E8 robust full-trajectory demands and lazy, bounded common-site generation."""
import hashlib,itertools,json,math,time
import numpy as np
import pandas as pd
from src.q3.e7_core import ROOT,Q3,E6,ResourceEngine,read,write_csv,write_json,load_pool,PROCESSED_DIR,RESULTS_Q2
from src.q3.link_budget import max_range_m,fspl_db
from src.q3.terrain_los import blocked_line_cells
from src.q3.relay_candidate_generator import TF
from src.q3.e52_geometry import safe_bbox,diameter_infeasible

OUT=Q3/'e8';E7=Q3/'e7'


def gamma_dir(gamma):return OUT/f'gamma_{int(gamma):02d}'


def direct_profile():
    target=OUT/'direct_profile_P01.csv'
    if target.exists():return read(target)
    e=ResourceEngine();flights=read(RESULTS_Q2/'pareto_schedules/P01/q2_sorties.csv');rows=[]
    for f in flights.itertuples():
        tr=e.trajectories['P01',f.sortie_id]
        times=tr.sample_times(f.takeoff_s,f.return_s,.5)
        cache={}
        def at(t):
            if t not in cache:
                xyz=tr.position([t])[0];ll=TF.transform(*xyz[:2]);blocked=blocked_line_cells(e.dem,*ll,xyz[2],*e.gll)
                margin=e.lm['transport<->G01']-fspl_db(e.pc.f_mhz,np.linalg.norm(xyz-e.gateway))-e.pc.l_obs_db*blocked
                cache[t]=(float(margin),bool(blocked))
            return cache[t]
        pending=[]
        for a,b in zip(times[:-1],times[1:]):
            va=at(float(a));vb=at(float(b))
            if va[1]!=vb[1] or any((va[0]>=g)!=(vb[0]>=g) for g in [0,2,4,6]):pending.append((float(a),float(b)))
        while pending:
            a,b=pending.pop()
            if b-a<=.05:continue
            mid=(a+b)/2;at(mid)
            for x,y in [(a,mid),(mid,b)]:
                vx=at(x);vy=at(y)
                if vx[1]!=vy[1] or any((vx[0]>=g)!=(vy[0]>=g) for g in [0,2,4,6]):pending.append((x,y))
        rows += [dict(transport_sortie_id=f.sortie_id,time_s=t,direct_margin_db=m,blocked=int(b)) for t,(m,b) in sorted(cache.items())]
    write_csv(target,rows);return pd.DataFrame(rows)


def derive_demands(gamma):
    frame=direct_profile();rows=[];flights=read(RESULTS_Q2/'pareto_schedules/P01/q2_sorties.csv').set_index('sortie_id')
    for sid,group in frame.groupby('transport_sortie_id',sort=True):
        g=group.sort_values('time_s');times=g.time_s.to_numpy();low=(g.direct_margin_db<gamma).to_numpy();intervals=[]
        begin=None
        for i,flag in enumerate(low):
            if flag and begin is None:begin=i
            if begin is not None and (not flag or i==len(low)-1):
                end=i if not flag else i+1
                a=max(float(flights.loc[sid].takeoff_s),float(times[max(0,begin-1)])-2.)
                b=min(float(flights.loc[sid].return_s),float(times[min(len(times)-1,end)])+2.)
                if intervals and a<=intervals[-1][1]:intervals[-1][1]=max(intervals[-1][1],b)
                else:intervals.append([a,b])
                begin=None
        for i,(a,b) in enumerate(intervals):
            aid=f'P01_GAMMA{int(gamma):02d}_{sid}_{i:02d}'
            rows.append(dict(atomic_task_id=aid,parent_gap_id=aid,pareto_id='P01',transport_sortie_id=sid,
                             service_start_s=a,service_end_s=b,service_duration_s=b-a,Gamma_C_db=gamma,
                             source='FULL_FLIGHT_DIRECT_PROFILE',construction_guard_s=2.))
    dest=gamma_dir(gamma);dest.mkdir(parents=True,exist_ok=True)
    config=json.loads((dest/'demand_config.json').read_text()) if (dest/'demand_config.json').exists() else {}
    if config.get('split_transport_ids'):
        split=[]
        for row in rows:
            count=math.ceil(row['service_duration_s']/config['max_atom_duration_s']) if row['transport_sortie_id'] in config['split_transport_ids'] else 1
            ends=np.linspace(row['service_start_s'],row['service_end_s'],count+1)
            for j,(a,b) in enumerate(zip(ends[:-1],ends[1:])):
                split.append(dict(row,atomic_task_id=row['atomic_task_id']+f'_A{j:02d}',service_start_s=float(a),service_end_s=float(b),service_duration_s=float(b-a)))
        rows=split
    write_csv(dest/'robust_tasks.csv',rows)
    write_json(dest/'demand_summary.json',dict(Gamma_C_db=gamma,tasks=len(rows),affected_transport_sorties=len({r['transport_sortie_id'] for r in rows}),
        guarded_service_sum_s=sum(r['service_duration_s'] for r in rows),base_step_s=.5,observed_boundary_refinement_s=.05,construction_guard_s=2.,
        threshold_applies_to='DIRECT_AND_BOTH_RELAY_HOPS',physical_fading_margin_unchanged=True,atomic_partition_config=config))
    return pd.DataFrame(rows)


class RobustEngine(ResourceEngine):
    def __init__(self,gamma):
        super().__init__();load_pool(self,'P01');self.gamma=float(gamma)
        # Internal margins are slack above Gamma. Exported records are converted
        # back to physical margins; frozen input link-budget files never change.
        self.lm={k:v-self.gamma for k,v in self.lm.items()}
        self.dtr=max_range_m(self.lm['transport<->relay'],self.pc,False)
        self.drg=max_range_m(self.lm['relay<->G01'],self.pc,False)
        task_file=gamma_dir(gamma)/'robust_tasks.csv'
        self.atoms=(read(task_file) if task_file.exists() else derive_demands(gamma)).set_index('atomic_task_id',drop=False)
        assert (self.atoms.Gamma_C_db==self.gamma).all(),'Cached tasks belong to a different Gamma'
        config_file=gamma_dir(gamma)/'demand_config.json'
        config=json.loads(config_file.read_text()) if config_file.exists() else {}
        summary=json.loads((gamma_dir(gamma)/'demand_summary.json').read_text())
        assert summary.get('atomic_partition_config',{})==config,'Partition config changed: explicitly rebuild demands and candidates'
        self.edges={'P01':{a:{} for a in self.atoms.index}};self.edge_cache.clear();self.search_log=[]
        self.accepted_sites=set(self.sites)

    def check_task(self,aid,sid):
        if (aid,sid) in self.edge_cache:return self.edge_cache[aid,sid]
        rec=super().check_task(aid,sid)
        if rec:
            rec['robust_slack_db']=rec['min_twohop_margin_db'];rec['Gamma_C_db']=self.gamma
            for key in ['min_access_margin_db','backhaul_margin_db','min_twohop_margin_db']:rec[key]+=self.gamma
        return rec

    def add_edges(self,sid):
        for aid,t in self.atoms.iterrows():
            tr=self.trajectories['P01',t.transport_sortie_id]
            if self.cheap(tr,[sid],t.service_start_s,t.service_end_s):
                rec=self.check_task(aid,sid)
                if rec:self.edges['P01'][aid][sid]=rec

    def common(self,tasks):return set.intersection(*(set(self.edges['P01'][a]) for a in tasks))

    def search_common(self,tasks,max_checks=1500,wanted=3,rank='coverage'):
        tasks=sorted(set(tasks));points=[];tick=time.monotonic()
        for aid in tasks:
            t=self.atoms.loc[aid];tr=self.trajectories['P01',t.transport_sortie_id]
            points.extend(tr.position(tr.vertices(t.service_start_s,t.service_end_s)))
        points=np.asarray(points);bbox=safe_bbox(points,self.dtr,self.drg,self.gateway)
        record=dict(tasks=tasks,checked=0,new_valid_sites=[],max_checks=max_checks,rank=rank)
        if bbox is None or diameter_infeasible(points,self.dtr):
            record['status']='EMPTY_COMMON_LOS_NECESSARY_REGION';self.search_log.append(record);return []
        x0,x1,y0,y1=bbox
        # Targeted necessary-region grid, ranked geometrically. No whole DEM scan.
        xs=np.arange(math.ceil(x0/120)*120,x1+1e-6,120);ys=np.arange(math.ceil(y0/120)*120,y1+1e-6,120)
        xy=np.array(list(itertools.product(xs,ys)),float)
        if not len(xy):return []
        worst=np.max(np.linalg.norm(xy[:,None,:]-points[None,:,:2],axis=2),axis=1)
        origin=np.linalg.norm(xy-self.gateway[:2],axis=1)
        valid=(worst<=self.dtr)&(origin<=self.drg)
        xy=xy[valid];score=origin[valid] if rank=='origin' else worst[valid]+.15*origin[valid];order=np.argsort(score,kind='stable')
        for i in order:
            for height in [300.,250.,200.]:
                s=self.add_site(*xy[i],height)
                if s is None:continue
                sid=s['site_id'];record['checked']+=1
                if self.backhaul(s)<0:continue
                good=True
                for aid in tasks:
                    t=self.atoms.loc[aid];tr=self.trajectories['P01',t.transport_sortie_id]
                    if not self.cheap(tr,[sid],t.service_start_s,t.service_end_s) or not self.check_task(aid,sid):good=False;break
                if good:
                    self.accepted_sites.add(sid);self.add_edges(sid);record['new_valid_sites'].append(sid)
                if len(record['new_valid_sites'])>=wanted or record['checked']>=max_checks:break
            if len(record['new_valid_sites'])>=wanted or record['checked']>=max_checks:break
        record.update(status='FOUND' if record['new_valid_sites'] else 'BOUNDED_SEARCH_EXHAUSTED',runtime_s=time.monotonic()-tick)
        self.search_log.append(record);print('COMMON',self.gamma,len(tasks),record['status'],record['checked'],flush=True)
        return record['new_valid_sites']

    def save(self):
        dest=gamma_dir(self.gamma);pairs=[r for ss in self.edges['P01'].values() for r in ss.values()]
        used=sorted({r['site_id'] for r in pairs});sites=[]
        for sid in used:
            s={k:v for k,v in self.sites[sid].items() if k!='static_energy'}
            if 'backhaul_margin_db' in s:s['backhaul_robust_slack_db']=s['backhaul_margin_db'];s['backhaul_margin_db']+=self.gamma
            sites.append(s)
        write_csv(dest/'candidate_pairs.csv',pairs);write_csv(dest/'candidate_sites.csv',sites)
        write_json(dest/'candidate_search.json',dict(Gamma_C_db=self.gamma,searches=self.search_log,counts=dict(self.stats),
            tasks=len(self.atoms),pairs=len(pairs),sites=len(sites),unresolved=[a for a,s in self.edges['P01'].items() if not s],candidate_set_complete=False))


def build_pool(gamma):
    derive_demands(gamma)
    e=RobustEngine(gamma)
    for sid in sorted(e.accepted_sites):e.add_edges(sid)
    for aid in e.atoms.index:
        if len(e.edges['P01'][aid])<2:e.search_common([aid],max_checks=1800,wanted=3)
    # Restore grouping possibilities around the actual E7 relay conflict units.
    baseline=json.loads((E7/'solutions/Q3E7_001/witness.json').read_text())
    old=read(E6/'guarded_atomic_tasks.csv').set_index('atomic_task_id')
    for g in baseline['groups']:
        transports={old.loc[a].transport_sortie_id for a in g['task_ids']}
        ids=list(e.atoms[e.atoms.transport_sortie_id.isin(transports)].atomic_task_id)
        if ids and not e.common(ids):e.search_common(ids,max_checks=1800,wanted=2)
    e.save();return e


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--gamma',type=float,required=True);a=p.parse_args();OUT.mkdir(exist_ok=True);build_pool(a.gamma)
