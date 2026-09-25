"""P1.4 epsilon-constrained autonomous full-pool candidate search."""
import argparse,math,time,sys,copy,os
from collections import defaultdict,Counter
from pathlib import Path
import pandas as pd
from ortools.sat.python import cp_model
from src.bench_p1_3b.common import ROOT,pool,tables,read,write,digest,signature,install_input_guard,ceil_units,UNITS
from src.bench_p1_3b.transport import build_cp,Collector,warm_hint
from src.bench_p1_3b.packages import materialize,workloads
from src.xb1.audit import export

OUT=ROOT/os.environ.get('P14_OUTPUT','results/p1_4')
BASE='842d950eba19374a287351b9b839fb446ff55d14'

def hint_trips(m,jobs,T,trips,p):
    chosen={(j['pattern'],j['copy']):j['start_units'] for j in trips}
    for j in jobs:
        active=(j['pattern'],j['copy']) in chosen
        m.AddHint(j['z'],int(active));m.AddHint(j['s'],chosen.get((j['pattern'],j['copy']),0))
    m.AddHint(T,max(j['start_units']+ceil_units(p['patterns'][j['pattern']]['duration']) for j in trips))

def execute(cap,axis,limit,count=None,prior=None):
    name=f'B{int(cap)}_{axis}'+('' if count is None else f'_N{count}')
    dest=OUT/'transport_runs'/name;dest.mkdir(parents=True,exist_ok=False)
    p=pool();t=tables();m,jobs,T,scale=build_cp(p,t,axis,cap=cap)
    if count is not None:m.Add(sum(j['z'] for j in jobs)==count)
    if prior:
        hint_trips(m,jobs,T,prior,p);hint=dict(source='Same phase autonomous incumbent',trip_count=len(prior))
    elif cap>=6500:
        hint=warm_hint(m,jobs,T,p)
    else:
        rep=read(ROOT/'results/p1_3b/representatives/T01.json');hint_trips(m,jobs,T,rep['trips'],p);hint=dict(source='P1.3-B T01',trip_count=27)
    m.ExportToFile(str(dest/'model.pbtxt'))
    write(dest/'config.json',dict(cap_s=cap,axis=axis,exact_transport_sorties=count,seed=26092511,workers=4,time_limit_s=limit,hint=hint,
        pool_sha256=digest(ROOT/'results/p1_3b/inputs/pattern_pool.json'),patterns=2903,optional_copies=len(jobs),
        J_late=0,time_grid_s=.1,bound_scope='Conservative transport grid only; Q3 constraints relaxed; not a continuous full-Q3 bound',
        purpose='Candidate generation for epsilon Q3 budget, no external target or arbitrary weighted objective'))
    solver=cp_model.CpSolver();solver.parameters.max_time_in_seconds=limit;solver.parameters.num_search_workers=4;solver.parameters.random_seed=26092511
    solver.parameters.log_search_progress=True;solver.parameters.log_to_stdout=False;logs=[];solver.log_callback=logs.append
    collector=Collector(jobs,dest,scale);cpu=time.process_time();wall=time.monotonic();status=solver.Solve(m,collector)
    good=status in [cp_model.OPTIMAL,cp_model.FEASIBLE]
    obj=solver.ObjectiveValue()/scale if good else None;bound=solver.BestObjectiveBound()/scale
    result=dict(name=name,status=solver.StatusName(status),incumbent=obj,raw_grid_bound=bound,gap=(obj-bound)/max(abs(obj),1e-9) if good else None,
        cpu_s=time.process_time()-cpu,wall_s=time.monotonic()-wall,nodes=solver.NumBranches(),conflicts=solver.NumConflicts(),iterations=None,
        structure_count=len(collector.seen),count=count,cap_s=cap,axis=axis,full_Q3_optimality_proven=False)
    (dest/'solver.log').write_text(''.join(logs));write(dest/'result.json',result);write(dest/'incumbent_trace.json',collector.rows)
    print('SEARCH',name,result,flush=True)
    rows=list(collector.seen.values());return sorted(rows,key=lambda r:r['objective_value'])

def export_candidate(row,ident,origin):
    dest=OUT/'q2/pareto_schedules'/ident;p=pool();t=tables();missions=materialize(row['trips'],p,t);metrics=export(missions,t,dest,ident)
    sys.path.insert(0,str(ROOT/'validation/mathematical'));from xb1_validate import check_package
    tick=time.process_time();v=check_package(dest,ident,pd.read_csv(ROOT/'results/reset/geometry/route_geometry.csv',float_precision='round_trip'))
    assert metrics['J_late']<=1e-8
    record=dict(id=ident,origin=origin,signature=row['structure_signature'],trips=row['trips'],pattern_occurrences=[x['pattern'] for x in row['trips']],
        metrics=metrics,package=str(dest.relative_to(ROOT)),validation_status=v['status'],validation_sha256=digest(dest/'validation.json'),validation_cpu_s=time.process_time()-tick,**workloads(missions,t))
    write(OUT/'representatives'/f'{ident}.json',record);print('Q2_VERIFIED',ident,metrics,flush=True)
    return record

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--limit',type=float,default=75);args=ap.parse_args();install_input_guard()
    selected={};records=[]
    for cap in [6500,6350,6250,6155]:
        rows=execute(cap,'sorties',args.limit)
        if not rows:continue
        best=rows[0];n=len(best['trips'])
        # Keep all newly attained integer-count levels in the requested region.
        for row in rows:
            if len(row['trips'])<=26:selected.setdefault(row['structure_signature'],(row,f'B{cap}_sorties'))
        energy=execute(cap,'energy',args.limit,count=n,prior=best['trips'])
        for row in energy[:2]:selected.setdefault(row['structure_signature'],(row,f'B{cap}_energy_N{n}'))
        # Export the growing selection so Q3 screening can start without waiting.
        known={r['signature'] for r in records}
        for key,(row,origin) in selected.items():
            if key not in known:
                ident=f'F{len(records)+1:02d}';records.append(export_candidate(row,ident,origin));known.add(key)
        write(OUT/'candidate_index.json',records)
    write(OUT/'transport_search_complete.json',dict(status='COMPLETED_BOUNDED_SEARCH',candidates=len(records),global_optimality_proven=False))
if __name__=='__main__':main()
