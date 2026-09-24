"""Independent review of the single bounded rescue and diagnostic scopes."""
from pathlib import Path
import hashlib,itertools,json,sys
import pandas as pd
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(Path(__file__).parent))
from e52_validate_candidates import IndependentAudit
OUT=ROOT/'results/q3/e81';OLD=ROOT/'results/q3/e8/gamma_06'
def read(p):return pd.read_csv(p,float_precision='round_trip')
def minimum_cover(tasks,edges):
    signatures={tuple(i for i,a in enumerate(tasks) if s in edges[a]) for s in set().union(*(edges[a] for a in tasks))}
    signatures=[set(x) for x in signatures if x];target=set(range(len(tasks)))
    for n in range(1,len(tasks)+1):
        if any(set().union(*xs)==target for xs in itertools.combinations(signatures,n)):return n
    return None
def main():
    manifest=json.loads((OUT/'input_manifest.json').read_text())
    for f,h in manifest['hashes'].items():assert hashlib.sha256((ROOT/f).read_bytes()).hexdigest()==h,f
    d=json.loads((OUT/'critical_window_diagnosis.json').read_text());search=json.loads((OUT/'feasibility_search.json').read_text());exp=json.loads((OUT/'candidate_expansion.json').read_text())
    assert search['search_attempts']==1 and exp['batches']==1 and search['arbitrary_per_aircraft_sortie_cap'] is None
    assert search['objective']=='FEASIBILITY_ONLY_ZERO_OBJECTIVE'
    assert search['status']=='GAMMA6_NO_WITNESS_FOUND' and search['physical_infeasibility_proven'] is False
    pairs=read(OLD/'candidate_pairs.csv');edges={a:set(f.site_id) for a,f in pairs.groupby('atomic_task_id')}
    for row in d['scanned_event_windows']:
        count=minimum_cover(row['active'],edges);assert count==row['minimum_full_atom_cover']
    assert all(x['minimum_full_atom_cover']<=2 for x in d['scanned_event_windows'][:-1])
    active=[x['atomic_task_id'] for x in d['active_robust_tasks']]
    assert minimum_cover(active,edges)==d['minimum_simultaneous_relays_under_full_interval_candidate_pool']==3
    audit=IndependentAudit();sites=read(OLD/'candidate_sites.csv').set_index('site_id');atoms=read(OLD/'robust_tasks.csv').set_index('atomic_task_id')
    shifts=read(ROOT/'results/q3/e7/solutions/Q3E7_001/transport_shifts_P01.csv').set_index('sortie_id').shift_s.to_dict();instant={}
    for a in active:
        task=atoms.loc[a];xyz=audit.position(('P01',task.transport_sortie_id),d['snapshot_time_s']-shifts[task.transport_sortie_id])
        instant[a]={s for s,row in sites.iterrows() if audit.backhaul(row)>=6 and audit.link(xyz,row)[0]>=6}
    assert minimum_cover(active,instant)==d['minimum_relays_at_physical_snapshot']==2
    fine=read(OUT/'robust_tasks.csv');coarse=read(OLD/'robust_tasks.csv')
    def union(rows):
        result=[]
        for a,b in sorted(zip(rows.service_start_s,rows.service_end_s)):
            if result and a<=result[-1][1]+1e-8:result[-1][1]=max(result[-1][1],b)
            else:result.append([a,b])
        return result
    for sid,part in coarse.groupby('transport_sortie_id'):assert union(part)==union(fine[fine.transport_sortie_id==sid])
    assert set(fine.atomic_task_id)==set(read(OUT/'candidate_pairs.csv').atomic_task_id)
    result=dict(status='GAMMA6_NO_WITNESS_FOUND',one_diagnosis_one_expansion_one_search=True,
        diagnosis_independently_checked=True,full_interval_reference_cover=3,physical_snapshot_cover=2,
        critical_window_scope='REFERENCE_SCHEDULE_AND_FULL_INTERVAL_CANDIDATE_RELATION_ONLY',
        guarded_demand_union_preserved=True,physical_infeasibility_proven=False,
        actual_solver_runtime_s=search['runtime_s'],configured_solver_limit_s=search['time_limit_s'],
        note='Solver wall-clock cleanup can exceed its configured internal limit; no second optimization call was made',
        Gamma_C_cert_db=4,E8_A='DONE',E8_B='OPTIONAL_RESCUE_CLOSED_UNRESOLVED',Q4_blocked_by_E8B=False)
    files=[p for p in OUT.glob('*') if p.is_file() and p.name!='validation.json' and p.suffix!='.log']
    files += [ROOT/'results/q3/E81_CRITICAL_WINDOW_REPORT.md',ROOT/'src/q3/e81_prepare.py',ROOT/'src/q3/e81_feasibility.py',Path(__file__)]
    result['artifact_sha256']={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    (OUT/'validation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='artifact_sha256'},indent=2))
if __name__=='__main__':main()
