"""Epsilon-budget searches, exact official-metric nondominance, and packaging."""
from src.q3.e7_search import *
from src.q3.e7_export import export_solution


def compare(a,b,tol):return -1 if a<b-tol else (1 if a>b+tol else 0)


def dominates(a,b):
    # TimelinessKey is one lexicographic criterion, not a weighted sum.
    c=compare(a['J_late'],b['J_late'],1e-4)
    if c==0:c=compare(a['J_norm'],b['J_norm'],1e-9)
    rest=[compare(a[k],b[k],1e-6 if k!='total_energy_kwh' else 1e-8)
          for k in ['joint_makespan_s','total_energy_kwh','transport_sorties','relay_sorties']]
    return c<=0 and all(x<=0 for x in rest) and (c<0 or any(x<0 for x in rest))


def unique_results(rows):
    seen=set();result=[]
    for r in rows:
        m=r['metrics'];key=tuple(round(m[k],6) for k in ['J_late','J_norm','joint_makespan_s','total_energy_kwh','transport_sorties','relay_sorties'])
        if key not in seen:seen.add(key);result.append(r)
    return result


def nondominated(rows):
    rows=unique_results(rows)
    return [r for i,r in enumerate(rows) if not any(i!=j and dominates(q['metrics'],r['metrics']) for j,q in enumerate(rows))]


def baseline(pid):
    r=json.loads((E6/f'selected_sorties_{pid}.json').read_text());shifts=json.loads((E6/f'shifts_{pid}.json').read_text())
    f=read(E6/f'transport_sorties_{pid}.csv');m=json.loads((E6/f'joint_metrics_{pid}.json').read_text())
    return dict(pareto_id=pid,groups=[dict(site_id=x['site_id'],task_ids=x['task_ids']) for x in r],sequences=sequences_for(r),
        shifts=shifts,selected=r,assignments={x.sortie_id:dict(uav_id=x.uav_id,battery_id=x.battery_id) for x in f.itertuples()},
        metrics=m,objective='baseline',J_late_budget=None,level='E6_BASELINE',resource_precedence_cuts=[])


def main():
    e=engine_for();best=json.loads((OUT/'best_timeliness.json').read_text())
    archive=json.loads((OUT/'timeliness_archive.json').read_text())
    # Complete a further bounded timeliness pass before fixing epsilon budgets.
    best,extra,info=search(e,best,rounds=3,repairs_per_round=24,label='TIMELINESS_REFINE')
    archive+=extra;write_json(OUT/'timeliness_refinement.json',info);write_json(OUT/'best_timeliness.json',best)
    anchor=best['metrics']['J_late'];requests=[]
    for eps in [0.,.01,.02,.05,.1]:
        for objective in ['makespan','energy','relay_sorties']:
            budget=(1+eps)*anchor
            eligible=[r for r in archive if r['metrics']['J_late']<=budget+1e-4]
            seed=min(eligible,key=lambda r:objective_key(r,objective))
            winner,extra,info=search(e,seed,objective,budget,rounds=2,repairs_per_round=12,label=f'EPS{eps}_{objective}')
            if winner:archive.append(winner)
            archive+=extra
            requests.append(dict(epsilon=eps,objective=objective,search_anchor_J_late=anchor,budget=budget,search=info))
            write_json(OUT/'epsilon_search.json',requests);write_json(OUT/'search_archive.json',unique_results(archive))
    archive += [baseline(p) for p in ['P01','P02','P03']]
    archive.append(json.loads((OUT/'free_order_seed.json').read_text()))
    rows=unique_results(archive);best=min(rows,key=lambda r:objective_key(r,'timeliness'));final_anchor=best['metrics']['J_late']
    frontier=nondominated(rows);frontier.sort(key=lambda r:objective_key(r,'timeliness'))
    manifest=[]
    for i,r in enumerate(frontier,1):
        sid=f'Q3E7_{i:03d}';engine=e if r['pareto_id']=='P01' else engine_for(r['pareto_id'])
        export_solution(engine,r,sid);manifest.append(dict(solution_id=sid,pareto_id=r['pareto_id'],**r['metrics']))
    write_csv(OUT/'provisional_pareto.csv',manifest)
    # A later secondary search can improve timeliness. Re-anchor every final
    # budget query against the actual best-known archive value, never an old seed.
    queries=[]
    for eps in [0.,.01,.02,.05,.1]:
        for objective in ['makespan','energy','relay_sorties']:
            eligible=[(i,r) for i,r in enumerate(frontier,1) if r['metrics']['J_late']<=(1+eps)*final_anchor+1e-4]
            i,r=min(eligible,key=lambda pair:objective_key(pair[1],objective))
            queries.append(dict(epsilon=eps,objective=objective,budget_metric='J_late',budget=(1+eps)*final_anchor,
                                solution_id=f'Q3E7_{i:03d}',attained_value=objective_key(r,objective)[0]))
    write_json(OUT/'budget_catalog_provisional.json',dict(best_known_TimelinessKey=[best['metrics']['J_late'],best['metrics']['J_norm']],
        search_anchor_J_late=anchor,final_anchor_J_late=final_anchor,queries=queries,
        semantics='BOUNDED_EPSILON_SEARCH_PLUS_EXACT_ARCHIVE_FILTER_AND_DETERMINISTIC_WITNESS_REPLAY'))
    write_json(OUT/'frontier_search_summary.json',dict(feasible_witnesses=len(rows),provisional_frontier=len(frontier),
        E6_SUPERSEDED=any(dominates(r['metrics'],baseline('P01')['metrics']) for r in rows),
        L2='NOT_ACTIVATED_L1_PROVIDES_SUBSTANTIAL_OFFICIAL_METRIC_IMPROVEMENT',L3='NOT_ACTIVATED',
        complete_global_pareto_frontier=False,all_final_points_require_independent_validation=True))
    write_json(OUT/'search_archive.json',rows)
    print('PROVISIONAL_FRONTIER',len(frontier),'best',best['metrics'],flush=True)


if __name__=='__main__':main()
