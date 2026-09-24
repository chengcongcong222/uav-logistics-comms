"""Reuse ordering witnesses across structurally matching P01/P02/P03 routes."""
from src.q3.e6_merge_search import *


def transfer(engine,source,target,selected):
    a=read(RESULTS_Q2/'pareto_schedules'/source/'q2_sorties.csv').set_index('sortie_id')
    b=read(RESULTS_Q2/'pareto_schedules'/target/'q2_sorties.csv').set_index('sortie_id')
    mapping={}
    for sid,g in engine.atoms[engine.atoms.pareto_id==source].groupby('transport_sortie_id'):
        dest=({'M001':'M002','M002':'M001'}.get(sid,sid) if ((source=='P02')!=(target=='P02')) else sid)
        # P02 reverses the initial S006/S007 visit order. This only proposes
        # a task grouping: target geometry and all intervals are rechecked.
        assert set(a.loc[sid].service_sequence.split('>'))==set(b.loc[dest].service_sequence.split('>'))
        h=engine.atoms[(engine.atoms.pareto_id==target)&(engine.atoms.transport_sortie_id==dest)]
        assert len(g)==len(h)
        mapping.update(zip(g.sort_values('service_start_s').atomic_task_id,h.sort_values('service_start_s').atomic_task_id))
    rows=[dict(r,task_ids=[mapping[x] for x in r['task_ids']]) for r in selected]
    if not all(engine.check_task(a,r['site_id']) for r in rows for a in r['task_ids']):return None,mapping
    return fixed_order_solution(engine,target,rows),mapping


def cross_plan(engine):
    snapshots={pid:json.loads((OUT/f'selected_sorties_{pid}.json').read_text()) for pid in ['P01','P02','P03']}
    for target,rows in snapshots.items():
        best=fixed_order_solution(engine,target,rows);attempts=[]
        for source,seed in snapshots.items():
            if source==target:continue
            answer,mapping=transfer(engine,source,target,seed)
            attempts.append(dict(source=source,target=target,atomic_mapping=mapping,
                                 total_shift_s=answer[0][0] if answer else None))
            if answer and answer[0]<best[0]:best=answer
        _,shifts,selected=best
        assign_and_save(engine,target,selected,shifts,'SHIFTED_SCHEDULE_FEASIBLE')
        write_csv(OUT/f'guarded_selected_pairs_{target}.csv',[engine.check_task(a,r['site_id']) for r in selected for a in r['task_ids']])
        write_json(OUT/f'cross_plan_{target}.json',attempts);export_plan(target)


if __name__=='__main__':
    e=ResourceEngine()
    for pid in ['P01','P02','P03']:load_pool(e,pid)
    apply_guards(e);cross_plan(e)
    for pid in ['P01','P02','P03']:merge_search(e,pid)
