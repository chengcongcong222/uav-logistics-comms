"""Three P1 Q3 flows on fresh transport and private communication templates."""
import hashlib,json,math,os,time
from collections import Counter
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.sparse import coo_matrix,csr_matrix,vstack
from src.bench_p1.common import OUT,ROOT,Preference,write,digest,signature,append
from src.reset.geometry import FlightDem,DATA
from src.reset.q3 import ResetEngine
from src.q3.e6_resources import ResourceEngine,read,write_csv
from src.q3.e52_geometry import SortieTrajectory
from src.q3.e8_candidates import RobustEngine
from src.q3.relay_candidate_generator import TF
from src.q3.terrain_los import blocked_line_cells
from src.q3.link_budget import fspl_db
import src.q3.e6_resources as resources
import src.q3.e7_core as core
import src.q3.e6_shift as shift
import src.q3.e6_export as exporter
import src.xb1.q3 as previous
from src.reset.cell_challenge import Cell
from src.q3.e8_seed_variants import partition
from src.bench_p1 import joint_kernel

class Engine(RobustEngine):
    energy=ResetEngine.energy
    def __init__(self,root,pid,stage):
        # Do not call ResourceEngine.__init__: it opens P01-P03 and E52 tasks.
        self.root=root;self.pid=pid;self.gamma=0.;self.search_log=[];self.geometry=FlightDem()
        self.dem=resources.Dem();self.pc,_=resources.load_comm_params();self.pr=resources.load_relay_params();self.lm=resources.pair_lmax()
        self.origin=np.array(resources.o01_pos());raw=json.loads((resources.PROCESSED_DIR/'communication_parameters.json').read_text())
        hg=float(raw['endpoints']['固定网关 G01']['天线离地高度（m）']['value'])
        self.gateway=self.origin+[0,0,hg];self.gll=(*TF.transform(*self.gateway[:2]),self.gateway[2])
        self.dtr=resources.max_range_m(self.lm['transport<->relay'],self.pc,False);self.drg=resources.max_range_m(self.lm['relay<->G01'],self.pc,False)
        self.sites={};self.access_cache={};self.position_cache={};self.stats=Counter();self.trajectories={};self.edge_cache={}
        self.base=root/'q2/pareto_schedules'/pid;self.dest=root/'q3'/pid;self.dest.mkdir(parents=True,exist_ok=True)
        dep=json.loads((OUT/'inputs/dependencies.json').read_text())
        self.dependencies=dict(common=dep,trajectory={p.name:digest(p) for p in self.base.glob('*') if p.suffix in ['.json','.csv']},sampling=dict(step=.5,boundary=.05,guard=2,gamma=0),private_root=str(root))
        self.fingerprint=signature(self.dependencies);write(self.dest/'cache_manifest.json',dict(fingerprint=self.fingerprint,dependencies=self.dependencies))
        frame=read(self.base/'transport_trace.csv')
        for sid in frame.task_id.unique():
            tr=SortieTrajectory(frame,pid,sid);self.trajectories[pid,sid]=tr;self.trajectories['P01',sid]=tr
        for row in json.loads((OUT/'inputs/common_sites.json').read_text()):self.add_site(row['x_m'],row['y_m'],row['agl_m'])
        self.accepted_sites=set(self.sites);stage('communication_templates')
        self.atoms=self.demands(frame).set_index('atomic_task_id',drop=False)
        edges={a:{} for a in self.atoms.index};self.edges={pid:edges,'P01':edges};stage('task_site_edges')
    def pool(self):
        # Fixed coordinate universe; no method-specific free historical pairs.
        for i,sid in enumerate(sorted(self.accepted_sites)):
            self.add_edges(sid)
            if i%10==0:write(self.dest/'pool_progress.json',dict(sites_checked=i+1,total_sites=len(self.accepted_sites),cpu_s=time.process_time()))
        pairs=[r for sites in self.edges[self.pid].values() for r in sites.values()]
        write_csv(self.dest/'candidate_pairs.csv',pairs)
        write_csv(self.dest/'candidate_sites.csv',[{k:v for k,v in s.items() if k!='static_energy'} for s in self.sites.values()])
        write(self.dest/'candidate_summary.json',dict(tasks=len(self.atoms),sites=len(self.sites),pairs=len(pairs),unresolved=[a for a in self.atoms.index if not self.common([a])],pool_scope='FROZEN_SHARED_SITE_COORDINATES'))

    def demands(self,frame):
        cache_root=self.root/'communication_templates';cache_root.mkdir(exist_ok=True);rows=[];log=[]
        specs={m['mission_id']:m for m in json.loads((self.base/'missions.json').read_text())};geometry_hash=hashlib.sha256((DATA/'manifest.json').read_bytes()).hexdigest()
        for f in read(self.base/'q2_sorties.csv').itertuples():
            m=specs[f.sortie_id];shape={k:m[k] for k in ['uav_type','box_ids','service_sequence','boxes_by_service','relative_takeoff_time','relative_delivery_times','relative_return_time']}
            signature=hashlib.sha256(json.dumps(dict(full_dependencies=self.fingerprint,shape=shape,geometry=geometry_hash,code=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),radio=hashlib.sha256((ROOT/'src/q3/terrain_los.py').read_bytes()).hexdigest()),sort_keys=True).encode()).hexdigest()
            file=cache_root/(signature+'.json');hit=file.exists()
            if hit:cached=json.loads(file.read_text())
            else:
                ff=frame[frame.task_id==f.sortie_id].copy();ff.time-=f.preparation_start_s;tr=SortieTrajectory(ff,self.pid,f.sortie_id);cache={}
                lo=f.takeoff_s-f.preparation_start_s;hi=f.return_s-f.preparation_start_s
                def at(t):
                    if t not in cache:
                        xyz=tr.position([t])[0];ll=TF.transform(*xyz[:2]);blocked=blocked_line_cells(self.dem,*ll,xyz[2],*self.gll);cache[t]=(float(self.lm['transport<->G01']-fspl_db(self.pc.f_mhz,np.linalg.norm(xyz-self.gateway))-self.pc.l_obs_db*blocked),bool(blocked))
                    return cache[t]
                times=tr.sample_times(lo,hi,.5);pending=[]
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
                        a=max(lo,ts[max(0,begin-1)]-2);b=min(hi,t+2)
                        if intervals and a<=intervals[-1][1]:intervals[-1][1]=max(b,intervals[-1][1])
                        else:intervals.append([a,b])
                        begin=None
                cached=dict(signature=signature,shape=shape,geometry=geometry_hash,intervals=intervals,samples=len(cache),step_s=.5,boundary_s=.05,guard_s=2.);write(file,cached)
            for j,(a,b) in enumerate(cached['intervals']):
                aid=f'{self.pid}_{f.sortie_id}_G{j:02d}';a+=f.preparation_start_s;b+=f.preparation_start_s
                rows.append(dict(atomic_task_id=aid,parent_gap_id=aid,pareto_id=self.pid,transport_sortie_id=f.sortie_id,service_start_s=a,service_end_s=b,service_duration_s=b-a,Gamma_C_db=0.,construction_guard_s=2.))
            log.append(dict(sortie_id=f.sortie_id,signature=signature,cache_hit=hit,intervals=len(cached['intervals'])));print('TEMPLATE',self.pid,f.sortie_id,hit,flush=True)
        write_csv(self.dest/'guarded_atomic_tasks.csv',rows);write(self.dest/'template_log.json',log);return pd.DataFrame(rows)

class ProjectedPreference:
    """Q3 transport seed uses the first four coordinates; relay count constant."""
    def __init__(self,parent):self.parent=parent;self.scales=parent.scales[:4]
    @property
    def weight(self):
        w=self.parent.weight[:4];s=sum(w)
        return [v/s for v in w] if s else [0,0,0,1]
    def event(self,action,**kw):self.parent.event(action,transport_projection=self.weight,**kw)

def preference_lp(model,sequences,cuts,preference,solver,exact=False):
    rows=list(model.rows);upper=list(model.upper);n=model.n
    for seq in sequences:
        for a,b in zip(seq[:-1],seq[1:]):rows.append({n+2*a+1:1,n+2*b:-1});upper.append(-model.tails[a]-model.leads[b])
    for i,j,gap in cuts:rows.append({i:1,j:-1});upper.append(-gap)
    rr=[];cc=[];vv=[]
    for i,row in enumerate(rows):
        for j,v in row.items():rr.append(i);cc.append(j);vv.append(v)
    mat=coo_matrix((vv,(rr,cc)),shape=(len(rows),model.dim)).tocsr();b=np.array(upper)
    # Prioritize lateness before optimizing declared preferences within that layer.
    first=solver(model.late_c,A_ub=mat,b_ub=b,bounds=model.bounds,method='highs');model.lp_solves+=1
    if not first.success:return None
    c=model.norm_c*preference.weight[0]/preference.scales[0];c[model.makespan]+=preference.weight[1]/preference.scales[1]
    if exact:c+=model.exact_c*preference.weight[2]/preference.scales[2]
    else:
        for j in range(model.k):
            power=model.e.pr['hover_power_kw']+model.e.pr['comm_power_kw']
            c[n+2*j]-=power/3600*preference.weight[2]/preference.scales[2];c[n+2*j+1]+=power/3600*preference.weight[2]/preference.scales[2]
    second=solver(c,A_ub=vstack([mat,csr_matrix(model.late_c)]),b_ub=np.r_[b,float(model.late_c@first.x)+1e-7],bounds=model.bounds,method='highs');model.lp_solves+=1
    result=second if second.success else first
    preference.event('q3_lp',exact_energy=exact,fixed_transport_sorties=model.n,fixed_relay_sorties=model.k,objective_coefficients_sha256=hashlib.sha256(c.tobytes()).hexdigest())
    return result.x,float(c@result.x)

def run(method,root,pool,base,tab,pref,patterns,remaining,milp,linprog,records,stage):
    patterns.solve(pool,'TRANSPORT_SEED',horizon=7200,step=180,limit=8,zero=True,single=True,preference=ProjectedPreference(pref))
    # All methods use the same newly generated candidate choice, never A11/XB.
    def trkey(r):
        m=r['metrics'];return (m['J_late'],m['J_norm'],m['makespan'],m['energy'],m['sorties'])
    chosen=min(records,key=trkey);pid=chosen['pid'];stage('fresh_q3_engine')
    e=Engine(root,pid,stage);e.pool()
    if any(not e.common([a]) for a in e.atoms.index):
        write(root/'q3_status.json',dict(status='NO_COMPLETE_LINK_COVER_IN_FIXED_POOL',infeasibility_proven=False));return
    core.RESULTS_Q2=root/'q2';shift.RESULTS_Q2=root/'q2';exporter.RESULTS_Q2=root/'q2'
    class Timing(core.Timing):
        def __init__(self,engine,_pid,groups):
            super().__init__(engine,pid,groups)
            if method=='SEQUENTIAL':
                for i in range(self.n):self.bounds[i]=(0.,0.)
        def lp(self,sequences,cuts):return preference_lp(self,sequences,cuts,pref,linprog)
    joint_kernel.Timing=Timing;joint_kernel.milp=milp
    class Challenge(Cell):
        def lp(self,sequences,cuts):return preference_lp(self,sequences,cuts,pref,linprog,exact=True)
    answers=[];flights=read(e.base/'q2_sorties.csv').sort_values(['preparation_start_s','sortie_id']);order=list(flights.sortie_id)
    def save(answer,origin):
        if remaining()<.5:raise TimeoutError('Q3 export budget')
        ident=f'Q3{len(answers)+1:04d}';previous.export(e,answer,ident);dest=e.dest/'solutions'/ident
        p=dest/f'joint_metrics_{pid}.json';m=json.loads(p.read_text());m.pop('external_structure_provenance',None);m.update(geometry_version='G2_UTM49N_STRAIGHT_NATIVE_SUPERCOVER_V1',source_provenance='FRESH_P1_TRANSPORT',development_only=True);write(p,m)
        write(dest/'input_manifest.json',dict(hashes={str(p.relative_to(ROOT)):digest(p) for p in e.base.glob('*') if p.is_file()},communication_dependencies=e.dependencies))
        if remaining()<0:raise TimeoutError('Q3 package late')
        records.append(dict(pid=ident,transport_pid=pid,scope='Q3',origin=origin,preference_id=pref.ident,cpu_ready_s=time.process_time(),metrics=m,package=str(dest)))
        write(root/'checkpoints.json',records);answers.append(answer)
    for batch in [8,6,12]:
        if remaining()<1:break
        groups=[]
        for start in range(0,len(order),batch):
            ids=list(e.atoms[e.atoms.transport_sortie_id.isin(order[start:start+batch])].atomic_task_id)
            if ids:groups+=partition(e,ids,'unit')
        stage('q3_resource_milp');answer,info=joint_kernel.relay_order_milp(e,groups,limit=8,joint_resources=True,preference=pref)
        append(root/'q3_attempts.jsonl',dict(method=method,preference_id=pref.ident,batch=batch,**info))
        if answer:
            save(answer,'FIXED_TRANSPORT_RELAY_REPAIR' if method=='SEQUENTIAL' else 'JOINT_TRANSPORT_RELAY_ADJUSTMENT')
            if method=='JOINT_CHALLENGE' and remaining()>1:
                stage('q3_active_challenge');candidate=Challenge(e,pid,answer,'timeliness').solve(answer['sequences'],node_limit=20)
                from src.q3.e7_pareto import dominates
                if candidate and dominates(candidate['metrics'],answer['metrics']):save(candidate,'Q3_ACTIVE_DOMINANCE_CHALLENGE')
        pref.next()
    write(root/'q3_status.json',dict(status='COMPLETE_WITNESSES_PENDING_AUDIT' if answers else 'NO_WITNESS_IN_BOUNDED_SEARCH',witnesses=len(answers),infeasibility_proven=False))
