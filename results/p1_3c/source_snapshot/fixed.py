"""Dynamic relay columns for fixed timings; exact finite-column resource master.

Pricing is a deterministic heuristic over site/time windows and LP-dual-guided
subsets. No global reduced-cost certificate is claimed.
"""
import argparse, itertools, math, time, warnings
import numpy as np
from scipy.optimize import linprog,milp,Bounds,LinearConstraint
from scipy.sparse import coo_matrix
from src.bench_p1_3c.common import *

FIELDS=('preparation_start_s','takeoff_s','service_start_s','service_end_s','return_s','uav_available_s','energy_ready_s','total_energy_kwh')

class Generator:
    def __init__(self,e,shifts):
        self.e=e;self.shifts=shifts;self.ids=list(e.atoms.index);self.index={a:i for i,a in enumerate(self.ids)}
        self.tasks={a:(float(r.service_start_s)+shifts[r.transport_sortie_id],float(r.service_end_s)+shifts[r.transport_sortie_id]) for a,r in e.atoms.iterrows()}
        self.static={s:e.energy(e.sites[s],0) for s in e.sites}
        self.by_site={s:[a for a in self.ids if s in e.common([a])] for s in e.sites}
        self.full=float(adapter.read(adapter.resources.PROCESSED_DIR/'relay_energy_components.csv').iloc[0].full_charge_time_s)
        self.columns={};self.checked=set()
    def build(self,s,ids):
        ids=tuple(sorted(ids));key=(s,ids)
        if not ids:return None
        # Lightweight exact counterpart, crosschecked on selected columns.
        p=self.e.pr;en=self.static[s];windows=sorted(self.tasks[a] for a in ids)
        start=windows[0][0];end=max(b for a,b in windows);active=0;right=-math.inf
        for a,b in windows:active+=max(0,b-max(a,right));right=max(right,b)
        energy=en['flight_energy_kwh']+en['setup_energy_kwh']+(end-start)*p['hover_power_kw']/3600+active*p['comm_power_kw']/3600
        takeoff=start-p['setup_time_s']-en['outbound_time_s'];prep=takeoff-p['prep_time_s']
        if prep< -1e-7 or energy>(1-p['rho'])*p['energy_kwh']+1e-9:return None
        from src.common.charging import charge_time_s
        ret=end+en['return_time_s'];charge=charge_time_s(1-energy/p['energy_kwh'],self.full)
        return dict(id=signature([s,ids]),site_id=s,task_ids=list(ids),endpoint_order=sorted([(self.tasks[a][k],k,a) for a in ids for k in [0,1]]),
            preparation_start_s=max(0,prep),takeoff_s=takeoff,service_start_s=start,service_end_s=end,return_s=ret,
            uav_available_s=ret+p['turnaround_time_s'],energy_ready_s=ret+charge,total_energy_kwh=energy,
            active_communication_s=active,outbound_time_s=en['outbound_time_s'],return_time_s=en['return_time_s'],charge_duration_s=charge)
    def add(self,s,ids):
        c=self.build(s,ids)
        if c:self.columns[c['id']]=c
    def seed(self):
        for s,ids in self.by_site.items():
            for a in ids:self.add(s,[a])
    def price(self,weights,round_id):
        before=len(self.columns)
        for s,ids in self.by_site.items():
            starts=sorted(set(self.tasks[a][0] for a in ids));ends=sorted(set(self.tasks[a][1] for a in ids))
            for lo in starts:
                for hi in ends:
                    if hi<lo:continue
                    group=[a for a in ids if self.tasks[a][0]>=lo-1e-8 and self.tasks[a][1]<=hi+1e-8]
                    if len(group)<2:continue
                    if round_id==0:self.add(s,group)
                    else:
                        # Dual-guided and negative-dual-filtered subsets are heuristic pricing.
                        ranked=sorted(group,key=lambda a:(-weights[self.index[a]],self.tasks[a][0],a))
                        if round_id%2:ranked=[a for a in ranked if weights[self.index[a]]>1e-7]
                        for k in range(2,len(ranked)+1):self.add(s,ranked[:k])
        return len(self.columns)-before

def matrix(gen,cols,artificial):
    n=len(gen.ids);rr=[];cc=[];vv=[];lower=[1.]*n;upper=[1.]*n;resource_rows=[]
    for j,c in enumerate(cols):
        for a in c['task_ids']:rr.append(gen.index[a]);cc.append(j);vv.append(1.)
    if artificial:
        for i in range(n):rr.append(i);cc.append(len(cols)+i);vv.append(1.)
    for begin,end,capacity in [('preparation_start_s','uav_available_s',2),('takeoff_s','energy_ready_s',6)]:
        points=sorted(set(c[begin] for c in cols));seen=set()
        for t in points:
            active=tuple(j for j,c in enumerate(cols) if c[begin]<=t+1e-8 and c[end]>t+1e-8)
            if active in seen or len(active)<=capacity:continue
            seen.add(active);row=len(lower);lower.append(-np.inf);upper.append(float(capacity))
            for j in active:rr.append(row);cc.append(j);vv.append(1.)
            resource_rows.append(dict(row=row,time=t,kind=begin,capacity=capacity))
    a=coo_matrix((vv,(rr,cc)),shape=(len(lower),len(cols)+(n if artificial else 0))).tocsr()
    return a,np.array(lower),np.array(upper),resource_rows

def clean(v):return None if v is None or not math.isfinite(float(v)) else float(v)

def nondominated_columns(columns):
    """Safe replacement for equal exact task sets, fixed timings only."""
    from collections import defaultdict
    groups=defaultdict(list)
    for c in columns:groups[tuple(c['task_ids'])].append(c)
    kept=[]
    def key(c):return (-c['preparation_start_s'],-c['takeoff_s'],c['uav_available_s'],c['energy_ready_s'],c['return_s'],c['total_energy_kwh'])
    for rows in groups.values():
        front=[]
        for c in sorted(rows,key=lambda c:(key(c),c['id'])):
            k=key(c)
            if any(all(x<=y for x,y in zip(key(d),k)) for d in front):continue
            front=[d for d in front if not all(x<=y for x,y in zip(k,key(d)))];front.append(c)
        kept+=front
    return kept

def solve_master(gen,cols,path,phase='count',limit=30):
    path.mkdir(parents=True,exist_ok=True);art=phase=='phase1';a,lo,hi,rows=matrix(gen,cols,art)
    c=np.r_[np.zeros(len(cols)),np.ones(len(gen.ids))] if art else np.ones(len(cols))
    write(path/'column_ids.json',[r['id'] for r in cols]);write(path/'resource_rows.json',rows)
    np.savez_compressed(path/'model.npz',data=a.data,indices=a.indices,indptr=a.indptr,shape=a.shape,lower=lo,upper=hi,objective=c)
    n=len(gen.ids);start=time.process_time();wall=time.monotonic()
    lp=linprog(c,A_ub=a[n:],b_ub=hi[n:],A_eq=a[:n],b_eq=hi[:n],bounds=(0,1),method='highs',options=dict(threads=1,time_limit=limit))
    record=dict(phase=phase,columns=len(cols),rows=a.shape[0],scope='EXACT_FIXED_TIMING_FINITE_GENERATED_COLUMNS; continuous binary64 occupation endpoints',
        lp_status=int(lp.status),lp_objective=clean(lp.fun),lp_cpu_s=time.process_time()-start,lp_wall_s=time.monotonic()-wall,lp_iterations=int(lp.nit),pricing_complete=False,global_bound=False)
    weights=lp.eqlin.marginals if lp.success else np.ones(n)
    start=time.process_time();wall=time.monotonic()
    from ortools.sat.python import cp_model
    model=cp_model.CpModel();z=[model.NewBoolVar('column_'+str(i)) for i in range(len(c))]
    for i in range(a.shape[0]):
        expr=sum(z[j] for j in a.indices[a.indptr[i]:a.indptr[i+1]])
        if lo[i]==hi[i]:model.Add(expr==int(hi[i]))
        else:model.Add(expr<=int(hi[i]))
    model.Minimize(sum(z[j] for j,v in enumerate(c) if v))
    if art:
        for j,v in enumerate(z):model.AddHint(v,int(j>=len(cols)))
    model.ExportToFile(str(path/'model.pbtxt'))
    solver=cp_model.CpSolver();solver.parameters.max_time_in_seconds=limit;solver.parameters.num_search_workers=1;solver.parameters.random_seed=SEED
    status=solver.Solve(model);feasible=status in [cp_model.OPTIMAL,cp_model.FEASIBLE]
    obj=solver.ObjectiveValue() if feasible else None;bound=solver.BestObjectiveBound() if status!=cp_model.MODEL_INVALID else None
    record.update(status=int(status),message=solver.StatusName(status),incumbent=obj,dual_bound=bound,gap=(obj-bound)/max(1,abs(obj)) if feasible else None,
        cpu_s=time.process_time()-start,wall_s=time.monotonic()-wall,nodes=solver.NumBranches(),conflicts=solver.NumConflicts(),solver='CP-SAT',
        response_stats=solver.ResponseStats())
    chosen=[]
    if feasible:
        values=np.array([solver.Value(v) for v in z]);np.save(path/'incumbent.npy',values);chosen=[r for j,r in enumerate(cols) if values[j]>.5]
        record['uncovered_tasks']=[gen.ids[i] for i in range(n) if art and values[len(cols)+i]>.5]
        if record['dual_bound'] is not None and record['dual_bound']>record['incumbent']+1e-5:record['bound_status']='BOUND_NOT_VALID';record['dual_bound']=None
    write(path/'result.json',record)
    return record,chosen,weights

def run(e,shifts,label,rounds=3,limit=25,fixed=False,guidance=None):
    root=e.root/label;root.mkdir(parents=True,exist_ok=False);tick=time.process_time();gen=Generator(e,shifts);gen.seed();log=[];weights=np.ones(len(gen.ids));chosen=[]
    write(root/'timings.json',shifts)
    if guidance:
        write(root/'master_guidance.json',guidance)
        for g in guidance:gen.add(g['site_id'],g['task_ids'])
    for k in range(rounds+1):
        added=0 if k==0 else gen.price(weights,k-1)
        cols=nondominated_columns(gen.columns.values());rec,selected,weights=solve_master(gen,cols,root/f'round_{k:02d}',phase='phase1',limit=limit)
        rec.update(round=k,added=added);log.append(rec);write(root/'iterations.json',log)
        print(e.pid,label,'round',k,'columns',len(cols),'uncovered',rec['incumbent'],flush=True)
        if rec['incumbent'] is not None and rec['incumbent']<.5:
            chosen=selected
            count,better,_=solve_master(gen,cols,root/'count_master',phase='count',limit=limit)
            if better:chosen=better
            log.append(count);break
    write(root/'columns.json',list(gen.columns.values()));write(root/'iterations.json',log)
    result=dict(pid=e.pid,label=label,fixed_transport=fixed,columns=len(gen.columns),iterations=log,witnesses=[],cpu_s=time.process_time()-tick,
        full_domain_infeasibility_proven=False,pricing='HEURISTIC_SITE_TIME_WINDOW_AND_LP_TASK_DUAL_SUBSETS',shifts=shifts)
    if chosen:
        for c in chosen:
            physical=sortie_column(e,e.pid,c['site_id'],c['task_ids'],shifts)
            assert physical and all(abs(c[f]-physical[f])<1e-7 for f in FIELDS)
        answer=materialize(e,chosen,shifts,fixed=fixed)
        result['witnesses']=[save_answer(e,answer,e.pid+'_'+label+'_Q3')]
    write(root/'result.json',result);return result,gen

def main():
    ap=argparse.ArgumentParser();ap.add_argument('pid');ap.add_argument('--rounds',type=int,default=3);ap.add_argument('--limit',type=float,default=25);args=ap.parse_args()
    install_input_guard();warnings.filterwarnings('ignore',message='Unrecognized options detected')
    e=engine(args.pid);shifts={r.sortie_id:0. for r in adapter.read(e.base/'q2_sorties.csv').itertuples()}
    run(e,shifts,'C1_FIXED',args.rounds,args.limit,True)
if __name__=='__main__':main()
