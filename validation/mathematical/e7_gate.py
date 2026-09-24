"""Independent E7 publication gate and official-metric frontier audit."""
from pathlib import Path
import hashlib,json,sys
import pandas as pd
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'results/q3/e7';E6=ROOT/'results/q3/e6'


def require(ok,message):
    if not ok:raise ValueError(message)


def verify_hashes(mapping):
    for name,digest in mapping.items():require(hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest,f'Stale artifact: {name}')


def dominates(a,b):
    # Independently implemented from the search-side filtering.
    if a['J_late']<b['J_late']-1e-4:timely=-1
    elif a['J_late']>b['J_late']+1e-4:timely=1
    else:
        timely=-1 if a['J_norm']<b['J_norm']-1e-9 else (1 if a['J_norm']>b['J_norm']+1e-9 else 0)
    if timely>0:return False
    strict=timely<0
    for k in ['joint_makespan_s','total_energy_kwh','transport_sorties','relay_sorties']:
        tol=1e-8 if k=='total_energy_kwh' else 1e-6
        if a[k]>b[k]+tol:return False
        strict |= a[k]<b[k]-tol
    return bool(strict)


def main():
    verify_hashes(json.loads((OUT/'input_manifest.json').read_text())['hashes'])
    requested=pd.read_csv(OUT/'provisional_pareto.csv');rows=[]
    for p in requested.itertuples():
        directory=OUT/'solutions'/p.solution_id
        result=json.loads((directory/f'validation_{p.pareto_id}_0.5.json').read_text())
        require(result['status']=='E7_PLAN_INDEPENDENTLY_VALIDATED',p.solution_id)
        require(result['hard_violations']==result['uncovered_sample_count']==0,'Hard or communication violation')
        require(len(result['relay_ids'])<=2 and len(result['energy_components'])<=6,'Relay capacity')
        verify_hashes(result['artifact_sha256'])
        m=json.loads((directory/f'joint_metrics_{p.pareto_id}.json').read_text())
        for k in ['J_late','J_norm','transport_energy_kwh']:require(abs(m[k]-result[k])<1e-4,k)
        fields=['J_late','J_norm','joint_makespan_s','transport_energy_kwh','relay_energy_kwh','total_energy_kwh',
                'transport_sorties','relay_sorties','total_transport_shift_s','total_absolute_transport_shift_s',
                'max_transport_shift_s','minimum_M_E_kwh']
        rows.append(dict(solution_id=p.solution_id,pareto_id=p.pareto_id,**{k:m[k] for k in fields},
                         minimum_M_C_db=result['minimum_twohop_margin_db'],hard_violations=0,uncovered_samples=0,
                         validation_status=result['status'],level=m['level']))
    require(bool(rows),'Empty validated frontier')
    for i,a in enumerate(rows):
        require(not any(i!=j and dominates(b,a) for j,b in enumerate(rows)),'Dominated point in final frontier')
    # Check the published frontier against every search/control witness, not
    # merely the fifteen epsilon query winners.
    archives=json.loads((OUT/'search_archive.json').read_text())+json.loads((OUT/'fixed_order_control_archive.json').read_text())
    for a in rows:require(not any(dominates(b['metrics'],a) for b in archives),'Unfiltered archive dominator')
    for b in archives:
        m=b['metrics']
        require(any(dominates(a,m) or all(abs(a[k]-m[k])<= (1e-4 if k=='J_late' else 1e-6) for k in ['J_late','J_norm','joint_makespan_s','total_energy_kwh','transport_sorties','relay_sorties']) for a in rows),'Missing archive nondominated point')
    replay=json.loads((OUT/'replay_checks.json').read_text())
    require(replay['status']=='ALL_FINAL_WITNESSES_REPLAYED','Replay failed')
    require({r['solution_id'] for r in replay['solutions']}=={r['solution_id'] for r in rows},'Replay coverage')
    require(json.loads((OUT/'regressions.json').read_text())['failures']==0,'Regression failure')
    for name in ['L1_RESOURCE_ABLATION','FIXED_ORDER_CONTROL']:
        r=json.loads((OUT/'solutions'/name/'validation_P01_0.5.json').read_text())
        require(r['status']=='E7_PLAN_INDEPENDENTLY_VALIDATED',name);verify_hashes(r['artifact_sha256'])
    rows.sort(key=lambda r:(r['J_late'],r['J_norm'],r['joint_makespan_s'],r['total_energy_kwh']))
    representative=rows[0]['solution_id'];r=json.loads((OUT/'solutions'/representative/'validation_P01_0.25.json').read_text())
    require(r['status']=='E7_PLAN_INDEPENDENTLY_VALIDATED','Sensitivity failure');verify_hashes(r['artifact_sha256'])
    pd.DataFrame(rows).to_csv(OUT/'pareto_solutions.csv',index=False)
    anchor=rows[0];metric='J_late' if anchor['J_late']>1e-8 else 'J_norm';queries=[]
    for eps in [0.,.01,.02,.05,.1]:
        for objective,key in [('makespan','joint_makespan_s'),('energy','total_energy_kwh'),('relay_sorties','relay_sorties')]:
            cap=(1+eps)*anchor[metric]
            eligible=[p for p in rows if p[metric]<=cap+1e-4 and (metric=='J_late' or p['J_late']<=1e-8)]
            winner=min(eligible,key=lambda p:(p[key],p['J_late'],p['J_norm'],p['joint_makespan_s'],p['total_energy_kwh'],p['solution_id']))
            queries.append(dict(epsilon=eps,objective=objective,budget_metric=metric,budget=cap,solution_id=winner['solution_id']))
    catalog=dict(best_known_TimelinessKey=[anchor['J_late'],anchor['J_norm']],queries=queries,
        mechanism='BOUNDED_EPSILON_SEARCH; VALIDATED_ARCHIVE_SELECTION; DETERMINISTIC_REPLAY_AND_REVALIDATION',global_frontier_proven=False)
    (OUT/'budget_catalog.json').write_text(json.dumps(catalog,indent=2)+'\n')
    baseline=json.loads((E6/'joint_metrics_P01.json').read_text())
    summary=dict(gate='E7_Q3_JOINT_PARETO_READY',base_commit='34e7dcb473f23cfe39a49c556a70a288d97b3b4d',
        validated_nondominated_points=len(rows),representative_solution=representative,
        E6_SUPERSEDED=any(dominates(p,baseline) for p in rows),L2_activated=False,L3_activated=False,
        Gamma_C_db=0.,global_frontier_proven=False,analytic_continuous_time_proof=False,next_stage_authorized=False,
        official_timeliness_order='LEXICOGRAPHIC_J_LATE_J_NORM',archive_metric_records_checked=len(archives),
        numerical_tolerances=dict(J_late=1e-4,J_norm=1e-9,time_s=1e-6,energy_kwh=1e-8))
    sources=list((ROOT/'src/q3').glob('e7_*.py'))+list((ROOT/'validation/mathematical').glob('e7_*.py'))
    summary['source_sha256']={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
    outputs=[p for p in OUT.rglob('*') if p.is_file() and p.suffix in ['.json','.csv'] and p!=OUT/'validation.json' and 'replay_tmp' not in p.parts and 'generated' not in p.parts]
    summary['output_sha256']={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in outputs}
    (OUT/'validation.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps({k:v for k,v in summary.items() if not k.endswith('sha256')},indent=2))


if __name__=='__main__':main()
