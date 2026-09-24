"""E7 L1: official-objective LP timing with free transport resource allocation.

Over-capacity interval cliques generate disjunctive precedence branches. A
bounded best-bound search returns checked feasible witnesses, never a global
optimality certificate. Relay grouping/site/order is an outer-search decision.
"""
import heapq,itertools,json,time
import numpy as np
from scipy.optimize import linprog
from scipy.sparse import coo_matrix
from src.q3.e6_resources import *
from src.q3.e6_run import load_pool
from src.q3.e6_shift import shift_transport_constraints

E6=OUT
OUT=Q3/'e7'


def engine_for(pid='P01'):
    e=ResourceEngine();load_pool(e,pid)
    e.atoms=read(E6/'guarded_atomic_tasks.csv').set_index('atomic_task_id',drop=False)
    e.edge_cache.clear()
    return e


def sequences_for(rows):
    return [sorted([i for i,r in enumerate(rows) if r['relay_id']==rid],key=lambda i:rows[i]['preparation_start_s']) for rid in ['R01','R02']]


def objective_key(result,objective):
    m=result['metrics']
    if objective=='timeliness':return (m['J_late'],m['J_norm'],m['joint_makespan_s'],m['total_energy_kwh'])
    key={'makespan':'joint_makespan_s','energy':'total_energy_kwh','relay_sorties':'relay_sorties'}[objective]
    return (m[key],m['J_late'],m['J_norm'],m['joint_makespan_s'],m['total_energy_kwh'])


def improves(a,b,objective):
    aa=objective_key(a,objective);bb=objective_key(b,objective)
    for x,y in zip(aa,bb):
        tol=1e-5 if max(abs(x),abs(y))>2 else 1e-9
        if x<y-tol:return True
        if x>y+tol:return False
    return False


class Timing:
    def __init__(self,engine,pid,groups,objective='timeliness',late_budget=None,fixed_transport_order=False):
        self.e=engine;self.pid=pid;self.groups=groups;self.objective=objective;self.budget=late_budget
        self.transport,limits,old_orders=shift_transport_constraints(pid)
        self.ids=list(self.transport.index);self.idx={s:i for i,s in enumerate(self.ids)}
        self.types=read(PROCESSED_DIR/'transport_uav_types.csv').set_index('uav_type')
        self.batteries=read(PROCESSED_DIR/'transport_batteries.csv').set_index('uav_type')
        self.uavs=read(PROCESSED_DIR/'transport_uavs.csv')
        self.delivery=read(RESULTS_Q2/'pareto_schedules'/pid/'q2_box_delivery.csv')
        raw=read(PROCESSED_DIR/'boxes.csv').set_index('box_id')
        self.weights=self.delivery.box_id.map(raw.priority_weight).to_numpy(float)
        self.deadlines=self.delivery.box_id.map(raw.expected_deadline_s).to_numpy(float)
        self.original_delivery=self.delivery.delivery_time_s.to_numpy(float)
        n=len(self.ids);k=len(groups);m=len(self.delivery);self.n=n;self.k=k;self.m=m
        self.late_offset=n+2*k;self.makespan=n+2*k+m;self.dim=self.makespan+1
        self.bounds=[]
        for sid,row in self.transport.iterrows():
            cap=40000-row.return_s
            boxes=self.delivery[self.delivery.sortie_id==sid]
            hard=boxes.hard_deadline_s-boxes.delivery_time_s
            if hard.notna().any():cap=min(cap,float(hard.min()))
            self.bounds.append((0. if fixed_transport_order else -row.preparation_start_s,cap))
        self.bounds += [(0,40000)]*(2*k)+[(0,None)]*m+[(0,40000)]
        self.rows=[];self.upper=[];self.leads=[];self.tails=[];self.initial=[];self.energy_constant=0.
        def add(row,rhs):self.rows.append(row);self.upper.append(rhs)
        for j,g in enumerate(groups):
            en=engine.energy(engine.sites[g['site_id']],0);p=engine.pr
            self.energy_constant+=en['total_energy_kwh']
            lead=p['prep_time_s']+en['outbound_time_s']+p['setup_time_s'];tail=en['return_time_s']+p['turnaround_time_s']
            self.leads.append(lead);self.tails.append(tail);self.bounds[n+2*j]=(lead,40000)
            for aid in g['task_ids']:
                t=engine.atoms.loc[aid];i=self.idx[t.transport_sortie_id]
                add({n+2*j:1,i:-1},float(t.service_start_s))
                add({n+2*j+1:-1,i:1},-float(t.service_end_s))
            span=((1-p['rho'])*p['energy_kwh']-en['total_energy_kwh'])*3600/(p['hover_power_kw']+p['comm_power_kw'])
            add({n+2*j+1:1,n+2*j:-1},span);add({n+2*j:1,n+2*j+1:-1},0)
            add({n+2*j+1:1,self.makespan:-1},-en['return_time_s'])
        for i,sid in enumerate(self.ids):add({i:1,self.makespan:-1},-self.transport.loc[sid].return_s)
        for j,r in enumerate(self.delivery.itertuples()):
            add({self.idx[r.sortie_id]:1,self.late_offset+j:-1},self.deadlines[j]-r.delivery_time_s)
        self.late_c=np.zeros(self.dim);self.late_c[self.late_offset:self.makespan]=self.weights
        self.norm_c=np.zeros(self.dim)
        for j,r in enumerate(self.delivery.itertuples()):self.norm_c[self.idx[r.sortie_id]]+=self.weights[j]/self.deadlines[j]/sum(self.weights)
        if late_budget is not None:add({self.late_offset+j:float(w) for j,w in enumerate(self.weights)},late_budget)
        if fixed_transport_order:
            for a,b,gap,_ in old_orders:add({self.idx[a]:1,self.idx[b]:-1},-gap)
        self.resource_specs=[]
        for kind in ['UAV','BATTERY']:
            for typ,rows in self.transport.groupby('uav_type'):
                specs=[]
                for sid,r in rows.iterrows():
                    charge=charge_time_s(1-r.energy_kwh/self.types.loc[typ].battery_energy_kwh,self.batteries.loc[typ].full_charge_time_s)
                    specs.append((self.idx[sid],float(r.preparation_start_s if kind=='UAV' else r.takeoff_s),float(r.return_s+(0 if kind=='UAV' else charge))))
                allowed=list(self.uavs[self.uavs.uav_type==typ].uav_id) if kind=='UAV' else [f'BAT-{typ}-{i:02d}' for i in range(1,int(self.batteries.loc[typ].battery_pool_count)+1)]
                self.resource_specs.append((kind,typ,specs,allowed))
        self.lp_solves=0

    def lp(self,sequences,cuts):
        rows=list(self.rows);upper=list(self.upper);n=self.n
        for seq in sequences:
            for a,b in zip(seq[:-1],seq[1:]):rows.append({n+2*a+1:1,n+2*b:-1});upper.append(-self.tails[a]-self.leads[b])
        for i,j,gap in cuts:rows.append({i:1,j:-1});upper.append(-gap)
        rr=[];cc=[];vv=[]
        for i,r in enumerate(rows):
            for j,v in r.items():rr.append(i);cc.append(j);vv.append(v)
        a=coo_matrix((vv,(rr,cc)),shape=(len(rows),self.dim)).tocsr();b=np.asarray(upper)
        c=self.late_c.copy()
        if self.objective=='makespan':c*=0;c[self.makespan]=1
        elif self.objective=='energy':
            c*=0
            for j in range(self.k):c[n+2*j]=-1.1/3600;c[n+2*j+1]=1.1/3600
        result=linprog(c,A_ub=a,b_ub=b,bounds=self.bounds,method='highs');self.lp_solves+=1
        if not result.success:return None
        if self.objective in ['timeliness','relay_sorties']:
            from scipy.sparse import vstack,csr_matrix
            second=linprog(self.norm_c,A_ub=vstack([a,csr_matrix(self.late_c)]),b_ub=np.r_[b,float(self.late_c@result.x)+1e-5],bounds=self.bounds,method='highs')
            self.lp_solves+=1
            if second.success:result=second
        return result.x,float(c@result.x)+(self.energy_constant if self.objective=='energy' else 0.)

    def conflict(self,x):
        for kind,typ,specs,allowed in self.resource_specs:
            for t in sorted(x[i]+start for i,start,end in specs):
                active=[s for s in specs if x[s[0]]+s[1]<=t+1e-6 and x[s[0]]+s[2]>t+1e-6]
                if len(active)>len(allowed):return active[:len(allowed)+1],kind,typ
        return None

    def materialize(self,x,sequences,cuts):
        shifts={s:float(x[i]) for i,s in enumerate(self.ids)};selected=[]
        for g in self.groups:
            row=sortie_column(self.e,self.pid,g['site_id'],g['task_ids'],shifts)
            if row is None:return None
            selected.append(row)
        try:
            color_intervals(selected,'preparation_start_s','uav_available_s',['R01','R02'],'relay_id')
            color_intervals(selected,'takeoff_s','energy_ready_s',[f'REC-{i:02d}' for i in range(1,7)],'energy_component_id')
            assignments={s:{} for s in self.ids}
            for kind,typ,specs,allowed in self.resource_specs:
                rs=[dict(sortie_id=self.ids[i],start=x[i]+a,end=x[i]+b) for i,a,b in specs]
                color_intervals(rs,'start','end',allowed,'resource')
                for r in rs:assignments[r['sortie_id']]['uav_id' if kind=='UAV' else 'battery_id']=r['resource']
        except ValueError:return None
        times=self.original_delivery+np.array([shifts[s] for s in self.delivery.sortie_id])
        late=float(np.sum(self.weights*np.maximum(0,times-self.deadlines)))
        if self.budget is not None and late>self.budget+1e-4:return None
        relaye=sum(r['total_energy_kwh'] for r in selected);transe=float(self.transport.energy_kwh.sum())
        metrics=dict(J_late=late,J_norm=float(np.sum(self.weights*times/self.deadlines)/sum(self.weights)),
            joint_makespan_s=max(max(self.transport.loc[s].return_s+d for s,d in shifts.items()),max(r['return_s'] for r in selected)),
            transport_energy_kwh=transe,relay_energy_kwh=relaye,total_energy_kwh=transe+relaye,
            transport_sorties=len(shifts),relay_sorties=len(selected),total_transport_shift_s=sum(shifts.values()),
            total_absolute_transport_shift_s=sum(abs(v) for v in shifts.values()),max_transport_shift_s=max(shifts.values()),
            minimum_M_E_kwh=min(r['energy_margin_kwh'] for r in selected))
        return dict(pareto_id=self.pid,groups=self.groups,sequences=sequences,shifts=shifts,selected=selected,
                    assignments=assignments,metrics=metrics,resource_precedence_cuts=[list(c) for c in cuts],
                    objective=self.objective,J_late_budget=self.budget,level='L1')

    def solve(self,sequences,node_limit=80):
        serial=itertools.count();queue=[];seen=set();popped=0
        # Greedy conflict repair evaluates every separating pair before choosing
        # its next cut. Hard deadlines remain in every LP, so impossible orders
        # are rejected instead of committing to a whole heuristic machine list.
        greedy_cuts=();greedy=self.lp(sequences,greedy_cuts)
        for _ in range(60):
            if greedy is None:break
            x,bound=greedy;conflict=self.conflict(x)
            if conflict is None:
                answer=self.materialize(x,sequences,greedy_cuts)
                if answer is not None:
                    answer['timing_search']=dict(lp_solves=self.lp_solves,nodes=0,node_limit=node_limit,scope='GREEDY_FREE_RESOURCE_CLIQUE_REPAIR',energy_surrogate=self.objective=='energy')
                    return answer
                break
            winner=None
            for a,b in itertools.permutations(conflict[0],2):
                cut=(a[0],b[0],float(a[2]-b[1])+1e-6)
                if cut in greedy_cuts:continue
                cs=greedy_cuts+(cut,);v=self.lp(sequences,cs)
                if v is not None:
                    score=(v[1],float(self.norm_c@v[0]))
                    if winner is None or score<winner[0]:winner=(score,cs,v)
            if winner is None:break
            _,greedy_cuts,greedy=winner
        # Deterministic list-scheduling warm start, with no inherited machine
        # IDs or orders. Each added order is only a search decision.
        cuts=();warm=self.lp(sequences,cuts)
        for _ in range(12):
            if warm is None:break
            x,bound=warm;conflict=self.conflict(x)
            if conflict is None:
                answer=self.materialize(x,sequences,cuts)
                if answer is not None:
                    answer['timing_search']=dict(lp_solves=self.lp_solves,nodes=0,node_limit=node_limit,scope='FREE_RESOURCE_LIST_SCHEDULING_AND_LP',energy_surrogate=self.objective=='energy')
                    return answer
                break
            _,kind,typ=conflict
            _,_,specs,allowed=next(s for s in self.resource_specs if s[0]==kind and s[1]==typ)
            ends=[0.]*len(allowed);last=[None]*len(allowed);new=list(cuts)
            for job in sorted(specs,key=lambda s:(round(x[s[0]]+s[1],5),self.bounds[s[0]][1],s[0])):
                r=min(range(len(allowed)),key=lambda r:(ends[r],r))
                if last[r] is not None:
                    a=last[r];new.append((a[0],job[0],round(a[2]-job[1],9)))
                ends[r]=max(ends[r],x[job[0]]+job[1])+job[2]-job[1];last[r]=job
            cuts=tuple(sorted(set(new)));warm=self.lp(sequences,cuts)
        def add(cuts):
            key=tuple(sorted(cuts))
            if key in seen:return
            seen.add(key);answer=self.lp(sequences,key)
            if answer is not None:heapq.heappush(queue,((answer[1],float(self.norm_c@answer[0]),-len(key)),next(serial),key,answer[0]))
        add(())
        while queue and popped<node_limit:
            bound,_,cuts,x=heapq.heappop(queue);popped+=1
            conflict=self.conflict(x)
            if conflict is None:
                answer=self.materialize(x,sequences,cuts)
                if answer is not None:
                    answer['timing_search']=dict(lp_solves=self.lp_solves,nodes=popped,node_limit=node_limit,scope='BOUNDED_RESOURCE_CLIQUE_BRANCH_SEARCH',energy_surrogate=self.objective=='energy')
                    return answer
                continue
            active,kind,typ=conflict
            # Any capacity-feasible arrangement must separate at least one
            # directed pair in an over-capacity clique. Explore every such pair.
            for a,b in itertools.permutations(active,2):
                cut=(a[0],b[0],round(a[2]-b[1],9))
                if cut not in cuts:add(cuts+(cut,))
        return None


def solve_seed(engine,pid='P01',objective='timeliness',late_budget=None,fixed=False,node_limit=80):
    rows=json.loads((E6/f'selected_sorties_{pid}.json').read_text())
    groups=[dict(site_id=r['site_id'],task_ids=r['task_ids']) for r in rows]
    return Timing(engine,pid,groups,objective,late_budget,fixed).solve(sequences_for(rows),node_limit)
