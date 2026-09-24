"""Bounded neighboring-sortie merges using fixed-site coverage and exact LP timing."""
import json,time
from src.q3.e6_guard import *
from src.q3.e6_order_search import OrderTiming,improve_orders
from src.q3.e6_export import export_plan


def fixed_order_solution(engine,pid,rows):
    groups=[dict(site_id=r['site_id'],task_ids=r['task_ids']) for r in rows]
    sequences=[sorted([i for i,r in enumerate(rows) if r['relay_id']==rid],key=lambda i:rows[i]['preparation_start_s']) for rid in ['R01','R02']]
    return OrderTiming(engine,pid,groups).solve(sequences)


def merge_search(engine,pid,budget_s=90):
    tick=time.monotonic();rows=json.loads((OUT/f'selected_sorties_{pid}.json').read_text())
    best=fixed_order_solution(engine,pid,rows);assert best is not None
    initial=best[0];history=[];attempts=0
    while time.monotonic()-tick<budget_s:
        rows=best[2];winner=None
        for rid in ['R01','R02']:
            order=sorted([i for i,r in enumerate(rows) if r['relay_id']==rid],key=lambda i:rows[i]['preparation_start_s'])
            for i,j in zip(order[:-1],order[1:]):
                ids=rows[i]['task_ids']+rows[j]['task_ids']
                candidates=set.intersection(*(set(engine.edges[pid][a]) for a in ids))
                def cost(sid):
                    en=engine.energy(engine.sites[sid],0)
                    return en['outbound_time_s']+en['return_time_s']
                for sid in sorted(candidates,key=cost)[:4]:
                    if not all(engine.check_task(a,sid) for a in ids):continue
                    trial=[dict(r) for k,r in enumerate(rows) if k!=j]
                    merged=next(r for r in trial if r is not rows[j] and r['task_ids']==rows[i]['task_ids'])
                    merged['task_ids']=ids;merged['site_id']=sid
                    answer=fixed_order_solution(engine,pid,trial);attempts+=1
                    if answer and answer[0][0]<best[0][0]-1e-5 and (winner is None or answer[0]<winner[0]):winner=answer
                    if time.monotonic()-tick>=budget_s:break
                if time.monotonic()-tick>=budget_s:break
        if winner is None:break
        best=winner
        history.append(dict(relay_sorties=len(best[2]),total_shift_s=best[0][0],max_shift_s=best[0][1],elapsed_s=time.monotonic()-tick))
        print('MERGE',pid,history[-1],flush=True)
    shifts,selected,order=improve_orders(engine,pid,best[2],budget_s=30)
    info=dict(initial_total_shift_s=initial[0],final_total_shift_s=sum(shifts.values()),attempts=attempts,
              runtime_s=time.monotonic()-tick,history=history,order_search=order,
              scope='BOUNDED_ADJACENT_SAME_RELAY_MERGES_TOP4_COMMON_SITES_NOT_GLOBAL_OPTIMUM')
    assign_and_save(engine,pid,selected,shifts,'SHIFTED_SCHEDULE_FEASIBLE')
    checks=[engine.check_task(a,r['site_id']) for r in selected for a in r['task_ids']]
    assert all(checks)
    write_csv(OUT/f'guarded_selected_pairs_{pid}.csv',checks)
    write_json(OUT/f'merge_search_{pid}.json',info);export_plan(pid)


if __name__=='__main__':
    engine=ResourceEngine()
    for pid in ['P01','P02','P03']:load_pool(engine,pid)
    apply_guards(engine)
    for pid in ['P01','P02','P03']:merge_search(engine,pid)
