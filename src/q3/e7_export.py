"""Write self-contained E7 L1 execution packages; E6 artifacts stay immutable."""
import shutil
from src.q3.e7_core import *
import src.q3.e6_export as legacy_export


def export_solution(engine,result,solution_id,destination=None):
    pid=result['pareto_id'];dest=Path(destination) if destination else OUT/'solutions'/solution_id;dest.mkdir(parents=True,exist_ok=True)
    if dest.resolve().parent==(OUT/'solutions').resolve():
        write_json(OUT/'validation.json',dict(gate='E7_VALIDATION_REQUIRED',changed_solution=solution_id,
                                            reason='Canonical execution rewritten; rerun independent audits'))
    for name in ['input_manifest.json','guarded_atomic_tasks.csv',f'candidate_sites_{pid}.csv']:
        shutil.copyfile(E6/name,dest/name)
    selected=result['selected']
    for i,r in enumerate(sorted(selected,key=lambda r:r['preparation_start_s']),1):r['relay_sortie_id']=f'{solution_id}_R{i:03d}'
    checks=[engine.check_task(a,r['site_id']) for r in selected for a in r['task_ids']]
    assert all(checks),'Guarded full-window candidate verification failed'
    write_csv(dest/f'guarded_selected_pairs_{pid}.csv',checks)
    write_json(dest/f'selected_sorties_{pid}.json',selected);write_json(dest/f'shifts_{pid}.json',result['shifts'])
    write_json(dest/f'plan_status_{pid}.json',dict(status='E7_CANDIDATE_PENDING_INDEPENDENT_VALIDATION'))
    old=legacy_export.OUT
    try:
        legacy_export.OUT=dest;legacy_export.export_plan(pid)
    finally:legacy_export.OUT=old
    flights=read(dest/f'transport_sorties_{pid}.csv')
    for i,r in flights.iterrows():
        for key in ['uav_id','battery_id']:flights.loc[i,key]=result['assignments'][r.sortie_id][key]
    write_csv(dest/f'transport_sorties_{pid}.csv',flights.to_dict('records'))
    for stem,key in [('transport_uav_calendar','uav_id'),('transport_battery_calendar','battery_id')]:
        frame=read(dest/f'{stem}_{pid}.csv')
        frame[key]=frame.sortie_id.map(lambda s:result['assignments'][s][key])
        write_csv(dest/f'{stem}_{pid}.csv',frame.to_dict('records'))
    metrics=json.loads((dest/f'joint_metrics_{pid}.json').read_text())
    for key,value in result['metrics'].items():
        if key in metrics:assert abs(metrics[key]-value)<1e-4,(key,metrics[key],value)
        metrics[key]=value
    margins=[min(r['min_access_margin_db'],r['backhaul_margin_db']) for r in checks]
    metrics.update(solution_id=solution_id,level=result['level'],search_objective=result['objective'],
                   J_late_budget=result['J_late_budget'],Gamma_C_db=0.,global_optimum_proven=False,
                   construction_guard_s=2.,communication_authority='INDEPENDENT_FULL_FLIGHT_AUDIT',
                   total_positive_transport_shift_s=sum(max(0,v) for v in result['shifts'].values()),
                   total_transport_advance_s=sum(max(0,-v) for v in result['shifts'].values()),
                   assignment_minimum_margin_quantiles_db={str(q):float(np.quantile(margins,q)) for q in [0,.25,.5,.75,1]})
    write_json(dest/f'joint_metrics_{pid}.json',metrics)
    write_json(dest/'witness.json',result)
    return dest


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--witness',required=True);p.add_argument('--id',required=True);a=p.parse_args()
    r=json.loads(Path(a.witness).read_text());export_solution(engine_for(r['pareto_id']),r,a.id)
