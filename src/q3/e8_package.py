"""Package a completed archive without repeating expensive search."""
from src.q3.e8_pareto import *

def package(gamma,export=True):
    dest=gamma_dir(gamma);rows=json.loads((dest/'search_archive.json').read_text())
    frontier=nondominated(rows);frontier.sort(key=lambda r:objective_key(r,'timeliness'))
    anchor=min(r['metrics']['J_late'] for r in rows);manifest=[]
    if export:
        e=load_engine(gamma)
        for i,r in enumerate(frontier,1):
            sid=f'Q3E8_G{int(gamma):02d}_{i:03d}';r['Gamma_C_db']=gamma
            export_solution(e,r,sid,dest/'solutions'/sid)
            manifest.append(dict(solution_id=sid,Gamma_C_db=gamma,**r['metrics']))
        write_csv(dest/'provisional_pareto.csv',manifest)
    queries=[]
    for eps in [0.,.01,.02,.05,.1]:
        for objective in ['makespan','energy','relay_sorties']:
            eligible=[(i,r) for i,r in enumerate(frontier,1) if r['metrics']['J_late']<=(1+eps)*anchor+1e-4]
            i,r=min(eligible,key=lambda pair:objective_key(pair[1],objective))
            queries.append(dict(epsilon=eps,objective=objective,budget_metric='J_late',budget=(1+eps)*anchor,
                solution_id=f'Q3E8_G{int(gamma):02d}_{i:03d}',attained_value=objective_key(r,objective)[0]))
    write_json(dest/'budget_catalog.json',dict(final_anchor_J_late=anchor,queries=queries,complete_global_pareto_frontier=False))
    write_json(dest/'scenario_status.json',dict(status='PARETO_PENDING_INDEPENDENT_VALIDATION',frontier=len(frontier),feasible_witnesses=len(rows)))
    print('PACKAGED',gamma,len(frontier),flush=True)

if __name__=='__main__':
    import sys
    package(float(sys.argv[1]),'--catalog-only' not in sys.argv)
