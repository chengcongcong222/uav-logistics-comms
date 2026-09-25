"""Whole-pool optional-interval scheduling; conservative 0.1 s primal domain.

All 2903 patterns compete in exact class coverage. Cumulative interval
constraints release all typed UAV/battery orders. Their assignments are
recovered by interval coloring, then the original independent audit runs.
CP bounds are NOT presented as continuous full-pool bounds.
"""
import argparse,copy,sys,time,math
from collections import defaultdict,Counter
import numpy as np
from ortools.sat.python import cp_model
from src.bench_p1_3b.common import *

def build_cp(p,t,axis,exclusions=(),cap=None):
    m=cp_model.CpModel();cl=p['classes'];patterns=p['patterns'];jobs=[];cover=defaultdict(list);intervals=defaultdict(list)
    H=ceil_units(max(max(0,r['zero_latest'])+r['duration'] for r in patterns)+1)
    T=m.new_int_var(0,H,'transport_makespan');den=sum(len(c['boxes'])*c['key'][5] for c in cl)
    scales={'makespan':UNITS,'sorties':1,'energy':10**9,'J_norm':10**12};objective=[]
    for i,r in enumerate(patterns):
        last=floor_units(min(r['hard_latest'],r['zero_latest']));previous=None
        for k in range(multiplicity(r,cl)):
            z=m.new_bool_var(f'p{i}_copy{k}');s=m.new_int_var(0,max(0,last),f's{i}_{k}')
            if last<0:m.add(z==0)
            m.add(s==0).only_enforce_if(z.Not())
            duration=ceil_units(r['duration']);prep=floor_units(r['prep']);tail=ceil_units(r['duration']+r['charge'])
            intervals[r['type'],'uav'].append(m.new_optional_fixed_size_interval_var(s,duration,z,f'u{i}_{k}'))
            intervals[r['type'],'battery'].append(m.new_optional_fixed_size_interval_var(s+prep,tail-prep,z,f'b{i}_{k}'))
            m.add(T>=s+duration).only_enforce_if(z)
            if previous is not None:
                m.add(previous[0]>=z);m.add(previous[1]<=s).only_enforce_if(z)
            previous=(z,s)
            for c,n in r['counts']:cover[c].append(n*z)
            if axis=='sorties':objective.append(z)
            elif axis=='energy':objective.append(round(r['energy']*scales[axis])*z)
            elif axis=='J_norm':
                const=sum(n*cl[c]['key'][5]*r['delivery'][str(c)]/cl[c]['key'][4] for c,n in r['counts'])/den
                slope=sum(n*cl[c]['key'][5]/cl[c]['key'][4] for c,n in r['counts'])/den/UNITS
                objective.extend([round(const*scales[axis])*z,round(slope*scales[axis])*s])
            jobs.append(dict(pattern=i,copy=k,z=z,s=s))
    for c,row in enumerate(cl):m.add(sum(cover[c])==len(row['boxes']))
    for typ in 'ABC':
        u=int((t['uavs'].uav_type==typ).sum());b=int(t['batteries'].set_index('uav_type').loc[typ].battery_pool_count)
        for kind,capacity in [('uav',u),('battery',b)]:m.add_cumulative(intervals[typ,kind],[1]*len(intervals[typ,kind]),capacity)
        workload=sum(ceil_units(patterns[j['pattern']]['duration'])*j['z'] for j in jobs if patterns[j['pattern']]['type']==typ)
        m.add(workload<=u*T)
    for chosen in exclusions:
        counts=Counter(chosen);selected=[j['z'] for j in jobs if j['copy']<counts[j['pattern']]]
        m.add(sum(selected)<=len(selected)-2) # at least two old pattern occurrences removed
    if cap is not None:m.add(T<=floor_units(cap))
    m.minimize(T if axis=='makespan' else sum(objective))
    return m,jobs,T,scales[axis]

def warm_hint(m,jobs,T,p):
    # Autonomous A11 only. Every hinted trip must match a frozen-pool pattern;
    # a hint does not restrict the model or certify feasibility.
    src=ROOT/'results/reset/q2/pareto_schedules/A11/missions.json'
    if not src.exists():return dict(used=False)
    box_class={b:c for c,r in enumerate(p['classes']) for b in r['boxes']};lookup={pattern_key(r):i for i,r in enumerate(p['patterns'])}
    chosen=defaultdict(list)
    for r in read(src):
        counts=Counter(box_class[b] for b in r['box_ids']);key=(r['uav_type'],tuple(r['service_sequence']),tuple(sorted(counts.items())))
        if key not in lookup:return dict(used=False,reason='A11 has a trip outside the pool')
        chosen[lookup[key]].append(r['preparation_start_s'])
    for starts in chosen.values():starts.sort()
    for j in jobs:
        active=j['copy']<len(chosen[j['pattern']]);m.add_hint(j['z'],int(active));m.add_hint(j['s'],round(chosen[j['pattern']][j['copy']]*UNITS) if active else 0)
    return dict(used=True,source=str(src.relative_to(ROOT)),sha256=digest(src),source_line='AUTONOMOUS_A11',role='HINT_ONLY_NOT_FIXED_OR_ADMITTED_AS_GRID_FEASIBLE')

class Collector(cp_model.CpSolverSolutionCallback):
    def __init__(self,jobs,dest,scale):super().__init__();self.jobs=jobs;self.dest=dest;self.scale=scale;self.rows=[];self.seen={}
    def on_solution_callback(self):
        trips=[dict(pattern=j['pattern'],copy=j['copy'],start_units=self.value(j['s'])) for j in self.jobs if self.boolean_value(j['z'])]
        key=signature(sorted(r['pattern'] for r in trips));val=self.objective_value/self.scale
        row=dict(structure_signature=key,trips=trips,objective_value=val,wall_s=self.wall_time,raw_bound=self.best_objective_bound/self.scale)
        if key not in self.seen or val<self.seen[key]['objective_value']:
            self.seen[key]=row
            write(self.dest/'candidate_structures.json',list(self.seen.values()))
        self.rows.append(dict(signature=key,objective_value=val,wall_s=self.wall_time))

def main():
    ap=argparse.ArgumentParser();ap.add_argument('axis',choices=AXES);ap.add_argument('--name');ap.add_argument('--limit',type=float,default=120);ap.add_argument('--exclude',nargs='*',default=[]);ap.add_argument('--cap',type=float);a=ap.parse_args()
    install_input_guard();dest=OUT/'transport_runs'/(a.name or a.axis)
    if dest.exists():raise RuntimeError('Refuse overwrite '+str(dest))
    dest.mkdir(parents=True);tick=time.process_time();p=pool();t=tables()
    exclusions=[]
    for name in a.exclude:
        rows=read(OUT/'transport_runs'/name/'candidate_structures.json');best=min(rows,key=lambda r:r['objective_value']);exclusions.append([j['pattern'] for j in best['trips']])
    m,jobs,T,scale=build_cp(p,t,a.axis,exclusions,a.cap);hint=warm_hint(m,jobs,T,p) if not exclusions else dict(used=False)
    config=dict(axis=a.axis,time_limit_s=a.limit,time_grid_s=1/UNITS,seed=26092511,workers=1,optional_trip_copies=len(jobs),patterns=len(p['patterns']),
        objective_scale=scale,objective='SINGLE_AXIS_INTEGER_COEFFICIENT_ROUNDING',transport_starts='All 0.1 s grid starts within original deadlines',
        conservative_intervals='UAV duration ceil; battery start floor(prep), end ceil(duration+charge)',
        cp_bound_scope='CONSERVATIVE_GRID_PRIMAL_DOMAIN_ONLY_NOT_A_CONTINUOUS_FULL_POOL_BOUND',
        no_external_threshold=True,near_optimal_cap=a.cap,excluded_prior_runs=a.exclude,hint=hint,
        source_hashes={str(f.relative_to(ROOT)):digest(f) for f in (ROOT/'src/bench_p1_3b').glob('*.py')})
    write(dest/'config.json',config);m.export_to_file(str(dest/'model.pbtxt'))
    solver=cp_model.CpSolver();solver.parameters.max_time_in_seconds=a.limit;solver.parameters.num_search_workers=1;solver.parameters.random_seed=26092511
    solver.parameters.log_search_progress=True;solver.parameters.log_to_stdout=False;logs=[];solver.log_callback=logs.append
    collector=Collector(jobs,dest,scale);start=time.process_time();status=solver.solve(m,collector);cpu=time.process_time()-start
    (dest/'solver.log').write_text(''.join(logs));write(dest/'incumbent_trace.json',collector.rows)
    val=solver.objective_value/scale if status in (cp_model.OPTIMAL,cp_model.FEASIBLE) else None
    bound=solver.best_objective_bound/scale
    result=dict(axis=a.axis,status=int(status),status_name=solver.status_name(status),solver_objective=val,raw_grid_bound=bound,
        raw_grid_relative_gap=None if val is None else max(0,(val-bound)/max(abs(val),1e-12)),cpu_s=cpu,wall_s=solver.wall_time,
        branches=solver.num_branches,conflicts=solver.num_conflicts,iterations=None,iterations_note='CP-SAT does not expose a single LP iteration count here',
        full_pool_continuous_optimality_proven=False,grid_optimal=status==cp_model.OPTIMAL,structure_count=len(collector.seen),total_process_cpu_s=time.process_time()-tick)
    write(dest/'result.json',result);print('CP_DONE',a.axis,result,flush=True)

if __name__=='__main__':main()
