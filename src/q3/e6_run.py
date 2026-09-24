"""Resumable E6 experiment driver; E52 input hashes are checked before reuse."""
import argparse
import hashlib
import json
import time
from pathlib import Path

from src.q3.e6_resources import *
from src.q3.e6_shift import optimize_shifts,transport_unit_partitions


def load_pool(engine,pid):
    for r in read(OUT/f'candidate_sites_{pid}.csv').to_dict('records'):
        s=engine.add_site(r['x_m'],r['y_m'],r['agl_m']);assert s['site_id']==r['site_id']
    for r in read(OUT/f'candidate_pairs_{pid}.csv').to_dict('records'):
        engine.edges[pid][r['atomic_task_id']][r['site_id']]=r


def assign_and_save(engine,pid,selected,shifts,status):
    color_intervals(selected,'preparation_start_s','uav_available_s',['R01','R02'],'relay_id')
    color_intervals(selected,'takeoff_s','energy_ready_s',[f'REC-{i:02d}' for i in range(1,7)],'energy_component_id')
    # A new witness invalidates any prior gate before schedules are exported.
    write_json(OUT/'validation.json',dict(gate='E6_VALIDATION_REQUIRED',changed_plan=pid,
                                        reason='Schedule rewritten; independent audits must be rerun'))
    for i,r in enumerate(sorted(selected,key=lambda r:r['preparation_start_s']),1):r['relay_sortie_id']=f'{pid}_R{i:03d}'
    write_json(OUT/f'selected_sorties_{pid}.json',selected)
    write_json(OUT/f'shifts_{pid}.json',shifts)
    write_json(OUT/f'plan_status_{pid}.json',dict(status=status,total_shift_s=sum(shifts.values()),
                                                max_shift_s=max(shifts.values()),relay_sorties=len(selected)))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--phase',choices=['b','c','all'],default='all')
    parser.add_argument('--plans',nargs='+',default=['P01','P02','P03']);args=parser.parse_args()
    OUT.mkdir(parents=True,exist_ok=True)
    gate=json.loads((Q3/'e52_rescue/validation.json').read_text());assert gate['gate']=='E5_Q3_RELAY_TASKS_READY'
    for f,h in gate['output_sha256'].items():assert hashlib.sha256((Q3/f).read_bytes()).hexdigest()==h,f
    inputs=[Q3/f for f in gate['output_sha256']]+[Q3/'e52_rescue/validation.json']
    inputs+=list(PROCESSED_DIR.glob('*.csv'))+[PROCESSED_DIR/'communication_parameters.json']
    for pid in ['P01','P02','P03']:inputs+=list((RESULTS_Q2/'pareto_schedules'/pid).glob('*'))
    hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs if p.is_file()}
    path=OUT/'input_manifest.json'
    if path.exists():assert json.loads(path.read_text())['hashes']==hashes,'Changed E6 input authority'
    else:write_json(path,dict(base_commit='6748710c905e6e380318b6768b5093d7128da9f6',hashes=hashes))
    engine=ResourceEngine();original={pid:diagnose(engine,pid) for pid in ['P01','P02','P03']}
    write_json(OUT/'level_a_diagnostics.json',original);write_json(OUT/'config.json',CONFIG)
    for pid in ['P01','P02','P03']:
        if (OUT/f'candidate_pairs_{pid}.csv').exists():load_pool(engine,pid)
    for pid in args.plans:
        if args.phase in ['b','all']:
            if not (OUT/f'candidate_pairs_{pid}.csv').exists():
                analysis=expand(engine,pid,original[pid]);save_pool(engine,pid)
            else:
                analysis=json.loads((OUT/f'conflict_analysis_{pid}.json').read_text())
                analysis['after']=diagnose(engine,pid)
            if 'resource_expansion' not in analysis:
                analysis['resource_expansion']=expand_resource_conflicts(engine,pid)
                analysis['after_resource_expansion']=diagnose(engine,pid)
                save_pool(engine,pid)
            cols=columns(engine,pid);write_json(OUT/f'columns_{pid}.json',cols)
            selected,info=solve_columns(cols,list(engine.edges[pid]));analysis['resource_solver']=info
            write_json(OUT/f'fixed_schedule_solver_{pid}.json',info)
            write_json(OUT/f'conflict_analysis_{pid}.json',analysis)
            if selected:
                selected=unique_assignment(engine,pid,selected)
                shifts={s:0. for s in read(RESULTS_Q2/'pareto_schedules'/pid/'q2_sorties.csv').sortie_id}
                assign_and_save(engine,pid,selected,shifts,'FIXED_SCHEDULE_FEASIBLE')
            print(f'LEVEL_B {pid}: peak_sites={analysis["after"]["peak_minimum_sites"]} MILP={info["status"]}',flush=True)
        if args.phase in ['c','all']:
            p=OUT/f'plan_status_{pid}.json'
            if p.exists() and json.loads(p.read_text())['status']=='FIXED_SCHEDULE_FEASIBLE':continue
            attempts=[];best=None
            # A bounded seed search; the committed execution witness provides
            # deterministic replay independent of MILP wall-clock outcomes.
            for groups in transport_unit_partitions(engine,pid):
                shifts,selected,info=optimize_shifts(engine,pid,groups,time_limit=60)
                attempts.append(dict(shift=info,
                                     groups=[dict(site_id=g['site_id'],task_ids=g['task_ids']) for g in groups]))
                print(f'LEVEL_C {pid}: groups={len(groups)} status={info["status"]} shift={info.get("total_shift_s")}',flush=True)
                if selected:
                    key=(sum(shifts.values()),max(shifts.values()),sum(c['total_energy_kwh'] for c in selected))
                    if best is None or key<best[0]:best=(key,shifts,selected)
                write_json(OUT/f'shift_transport_unit_search_{pid}.json',attempts)
            if best:
                assign_and_save(engine,pid,best[2],best[1],'SHIFTED_SCHEDULE_FEASIBLE')
            else:
                # A failed new search must not erase an existing feasible witness.
                if not (OUT/f'selected_sorties_{pid}.json').exists():
                    write_json(OUT/f'plan_status_{pid}.json',dict(status='FIXED_TRANSPORT_STRUCTURE_INFEASIBLE_UNDER_CURRENT_SEARCH',
                                                                 interpretation='NOT_A_PHYSICAL_OR_GLOBAL_INFEASIBILITY_PROOF'))
        write_json(OUT/'engine_counts.json',dict(engine.stats))


if __name__=='__main__':main()
