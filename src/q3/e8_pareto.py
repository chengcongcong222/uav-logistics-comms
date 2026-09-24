"""Apply the frozen E7 epsilon generator separately to each robust scenario."""
from src.q3.e8_search import *
from src.q3.e8_export import export_solution

def run(gamma):
    dest=gamma_dir(gamma);e=load_engine(gamma)
    seed=json.loads((dest/'seed.json').read_text());archive=[seed];logs=[]
    best,extra,info=search(e,seed,rounds=4,repairs_per_round=28,label=f'G{gamma}_TIMELINESS')
    archive+=extra;archive.append(best);logs.append(info)
    best,extra,info=search(e,best,rounds=3,repairs_per_round=24,label=f'G{gamma}_REFINE')
    archive+=extra;archive.append(best);logs.append(info)
    anchor=best['metrics']['J_late'];requests=[]
    write_json(dest/'timeliness_search.json',logs)
    for eps in [0.,.01,.02,.05,.1]:
        for objective in ['makespan','energy','relay_sorties']:
            budget=(1+eps)*anchor
            eligible=[r for r in archive if r['metrics']['J_late']<=budget+1e-4]
            initial=min(eligible,key=lambda r:objective_key(r,objective))
            winner,extra,info=search(e,initial,objective,budget,rounds=2,repairs_per_round=12,label=f'G{gamma}_EPS{eps}_{objective}')
            if winner:archive.append(winner)
            archive+=extra
            requests.append(dict(epsilon=eps,objective=objective,search_anchor_J_late=anchor,budget=budget,search=info))
            write_json(dest/'epsilon_search.json',requests);write_json(dest/'search_archive.json',unique_results(archive))
    rows=unique_results(archive);frontier=nondominated(rows);frontier.sort(key=lambda r:objective_key(r,'timeliness'))
    final_anchor=min(r['metrics']['J_late'] for r in rows);manifest=[]
    for i,r in enumerate(frontier,1):
        sid=f'Q3E8_G{int(gamma):02d}_{i:03d}';r['Gamma_C_db']=gamma
        export_solution(e,r,sid,dest/'solutions'/sid)
        manifest.append(dict(solution_id=sid,Gamma_C_db=gamma,**r['metrics']))
    write_csv(dest/'provisional_pareto.csv',manifest)
    queries=[]
    for eps in [0.,.01,.02,.05,.1]:
        for objective in ['makespan','energy','relay_sorties']:
            eligible=[(i,r) for i,r in enumerate(frontier,1) if r['metrics']['J_late']<=(1+eps)*final_anchor+1e-4]
            i,r=min(eligible,key=lambda pair:objective_key(pair[1],objective))
            queries.append(dict(epsilon=eps,objective=objective,budget_metric='J_late',budget=(1+eps)*final_anchor,
                solution_id=f'Q3E8_G{int(gamma):02d}_{i:03d}',attained_value=objective_key(r,objective)[0]))
    write_json(dest/'budget_catalog.json',dict(search_anchor_J_late=anchor,final_anchor_J_late=final_anchor,queries=queries,
        complete_global_pareto_frontier=False,semantics='E7_BOUNDED_EPSILON_GENERATOR_AT_FIXED_GAMMA'))
    write_json(dest/'scenario_status.json',dict(status='PARETO_PENDING_INDEPENDENT_VALIDATION',frontier=len(frontier),feasible_witnesses=len(rows)))
    print('PARETO',gamma,len(frontier),manifest,flush=True)

if __name__=='__main__':
    import sys
    run(float(sys.argv[1]))
