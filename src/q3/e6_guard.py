"""E6-only guards for inherited discretized outage boundaries (E52 unchanged)."""
import json
from src.q3.e6_resources import *
from src.q3.e6_run import load_pool,assign_and_save
from src.q3.e6_order_search import improve_orders


def apply_guards(engine,padding_s=2.):
    original=engine.atoms.copy()
    for aid,t in original.iterrows():
        base=read(RESULTS_Q2/'pareto_schedules'/t.pareto_id/'q2_sorties.csv').set_index('sortie_id').loc[t.transport_sortie_id]
        engine.atoms.loc[aid,'service_start_s']=max(base.takeoff_s,t.service_start_s-padding_s)
        engine.atoms.loc[aid,'service_end_s']=min(base.return_s,t.service_end_s+padding_s)
    engine.atoms['service_duration_s']=engine.atoms.service_end_s-engine.atoms.service_start_s
    engine.edge_cache.clear()
    write_csv(OUT/'guarded_atomic_tasks.csv',engine.atoms.to_dict('records'))
    write_json(OUT/'boundary_guard_config.json',dict(padding_s=padding_s,reason='Full-flight audit exposed inherited gap starts up to 1.11 seconds late',
              authority='E6_DERIVED_ONLY_E52_UNCHANGED',certificate='NUMERICAL_FULL_FLIGHT_CHECK_REQUIRED'))


def repair_plan(engine,pid):
    selected=json.loads((OUT/f'selected_sorties_{pid}.json').read_text());checks=[]
    for row in selected:
        if not all(engine.check_task(aid,row['site_id']) for aid in row['task_ids']):
            choices=[]
            for sid in sorted(engine.sites):
                if all(engine.check_task(aid,sid) for aid in row['task_ids']):
                    en=engine.energy(engine.sites[sid],0)
                    choices.append((en['outbound_time_s']+en['return_time_s'],sid))
            if not choices:raise ValueError(f'No guarded common site for {pid} {row["task_ids"]}')
            previous=row['site_id'];row['site_id']=min(choices)[1]
            print('GUARD_SITE_CHANGE',pid,previous,row['site_id'],row['task_ids'],flush=True)
        for aid in row['task_ids']:
            rec=engine.check_task(aid,row['site_id'])
            if rec is None:raise ValueError(f'Guard invalidated selected candidate {pid} {aid} {row["site_id"]}')
            checks.append(rec)
    # Same aircraft orders; LP includes the larger guarded service intervals.
    shifts,selected,info=improve_orders(engine,pid,selected)
    assign_and_save(engine,pid,selected,shifts,'SHIFTED_SCHEDULE_FEASIBLE')
    write_json(OUT/f'guard_order_search_{pid}.json',info)
    write_csv(OUT/f'guarded_selected_pairs_{pid}.csv',checks)
    print('GUARDED',pid,info,flush=True)


if __name__=='__main__':
    engine=ResourceEngine()
    for pid in ['P01','P02','P03']:load_pool(engine,pid)
    apply_guards(engine)
    for pid in ['P01','P02','P03']:repair_plan(engine,pid)
