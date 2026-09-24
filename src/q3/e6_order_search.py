"""Fast exact LP timing for fixed relay orders, with deterministic local search."""
from __future__ import annotations
import time
import numpy as np
from scipy.optimize import linprog
from scipy.sparse import coo_matrix,hstack,vstack,csr_matrix

from src.q3.e6_shift import shift_transport_constraints
from src.q3.e6_resources import sortie_column,color_intervals


class OrderTiming:
    def __init__(self,engine,pid,groups):
        self.engine=engine;self.pid=pid;self.groups=groups
        transport,limits,precedence=shift_transport_constraints(pid)
        self.ids=list(transport.index);self.idx={s:i for i,s in enumerate(self.ids)}
        n=len(self.ids);k=len(groups);self.n=n;self.k=k
        self.leads=[];self.tails=[];rows=[];upper=[]
        self.bounds=[(0,max(0.,limits[s])) for s in self.ids]+[(0,40000)]*(2*k)
        def add(values,rhs):rows.append(values);upper.append(rhs)
        for a,b,gap,_ in precedence:add({self.idx[a]:1,self.idx[b]:-1},-gap)
        for j,g in enumerate(groups):
            en=engine.energy(engine.sites[g['site_id']],0)
            lead=engine.pr['prep_time_s']+en['outbound_time_s']+engine.pr['setup_time_s']
            tail=en['return_time_s']+engine.pr['turnaround_time_s']
            self.leads.append(lead);self.tails.append(tail);self.bounds[n+2*j]=(lead,40000)
            for aid in g['task_ids']:
                task=engine.atoms.loc[aid];delta=self.idx[task.transport_sortie_id]
                add({n+2*j:1,delta:-1},float(task.service_start_s))
                add({n+2*j+1:-1,delta:1},-float(task.service_end_s))
            maxspan=((1-engine.pr['rho'])*engine.pr['energy_kwh']-en['total_energy_kwh'])*3600/(engine.pr['hover_power_kw']+engine.pr['comm_power_kw'])
            add({n+2*j+1:1,n+2*j:-1},maxspan)
            add({n+2*j:1,n+2*j+1:-1},0)
        self.rows=rows;self.upper=upper;self.cache={};self.solves=0

    def solve(self,sequences,lexicographic=False):
        key=(tuple(tuple(s) for s in sequences),lexicographic)
        if key in self.cache:return self.cache[key]
        rows=list(self.rows);upper=list(self.upper);n=self.n;k=self.k
        for seq in sequences:
            for a,b in zip(seq[:-1],seq[1:]):
                rows.append({n+2*a+1:1,n+2*b:-1});upper.append(-self.tails[a]-self.leads[b])
        rr=[];cc=[];vv=[]
        for i,row in enumerate(rows):
            for j,v in row.items():rr.append(i);cc.append(j);vv.append(v)
        matrix=coo_matrix((vv,(rr,cc)),shape=(len(rows),n+2*k)).tocsr()
        result=linprog(np.r_[np.ones(n),np.zeros(2*k)],A_ub=matrix,b_ub=np.array(upper),bounds=self.bounds,method='highs')
        self.solves+=1
        if not result.success:self.cache[key]=None;return None
        if lexicographic:
            # Exact second objective for this grouping and these fixed orders.
            # The 1e-7 s allowance is solely a numerical feasibility tolerance.
            dimension=n+2*k
            expanded=hstack([matrix,csr_matrix((matrix.shape[0],1))],format='csr')
            extra=np.zeros((n+1,dimension+1));extra[0,:n]=1
            for i in range(n):extra[i+1,i]=1;extra[i+1,-1]=-1
            second=linprog(np.r_[np.zeros(dimension),1.],
                A_ub=vstack([expanded,csr_matrix(extra)],format='csr'),
                b_ub=np.r_[upper,result.fun+1e-7,np.zeros(n)],
                bounds=self.bounds+[(0,None)],method='highs')
            self.solves+=1
            if not second.success:self.cache[key]=None;return None
            result=second
        shifts={s:max(0.,float(result.x[i])) for i,s in enumerate(self.ids)}
        selected=[]
        for group in self.groups:
            row=sortie_column(self.engine,self.pid,group['site_id'],group['task_ids'],shifts)
            if row is None:self.cache[key]=None;return None
            selected.append(row)
        try:
            color_intervals(selected,'preparation_start_s','uav_available_s',['R01','R02'],'relay_id')
            color_intervals(selected,'takeoff_s','energy_ready_s',[f'REC-{i:02d}' for i in range(1,7)],'energy_component_id')
        except ValueError:self.cache[key]=None;return None
        value=(sum(shifts.values()),max(shifts.values()),sum(r['total_energy_kwh'] for r in selected))
        answer=(value,shifts,selected);self.cache[key]=answer;return answer


def improve_orders(engine,pid,selected,budget_s=60):
    tick=time.monotonic();groups=[dict(site_id=r['site_id'],task_ids=r['task_ids']) for r in selected]
    sequences=[]
    for rid in ['R01','R02']:
        sequences.append(sorted([i for i,r in enumerate(selected) if r['relay_id']==rid],key=lambda i:selected[i]['preparation_start_s']))
    timing=OrderTiming(engine,pid,groups);best=timing.solve(sequences)
    assert best is not None,'Seed ordering should be feasible'
    initial=best[0];history=[];iterations=0
    while time.monotonic()-tick<budget_s:
        improved=None;best_sequences=None
        # Single-job insertion on either relay (including same-relay reorder).
        for src in range(2):
            for at,job in enumerate(sequences[src]):
                for dst in range(2):
                    for pos in range(len(sequences[dst])+1):
                        trial=[list(s) for s in sequences];trial[src].pop(at)
                        trial[dst].insert(min(pos,len(trial[dst])),job)
                        result=timing.solve(trial)
                        if result and result[0]<best[0] and (improved is None or result[0]<improved[0]):
                            improved=result;best_sequences=trial
                        if time.monotonic()-tick>=budget_s:break
                    if time.monotonic()-tick>=budget_s:break
                if time.monotonic()-tick>=budget_s:break
            if time.monotonic()-tick>=budget_s:break
        iterations+=1
        if improved is None:break
        best=improved;sequences=best_sequences
        history.append(dict(iteration=iterations,total_shift_s=best[0][0],max_shift_s=best[0][1],elapsed_s=time.monotonic()-tick))
        print(f'ORDER_SEARCH {pid} {history[-1]}',flush=True)
    refined=timing.solve(sequences,lexicographic=True)
    if refined is not None:best=refined
    info=dict(initial_total_shift_s=initial[0],final_total_shift_s=best[0][0],max_shift_s=best[0][1],
              lp_solves=timing.solves,iterations=iterations,runtime_s=time.monotonic()-tick,history=history,
              scope='LP_OPTIMAL_TIMING_FOR_SELECTED_ORDERS; BOUNDED_SINGLE_JOB_INSERTION_SEARCH, NOT_GLOBAL_OPTIMUM')
    return best[1],best[2],info
