"""Bind XB1 source, local physics, independent audits, replays and comparisons."""
import hashlib,json,sys
from pathlib import Path
import pandas as pd
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from src.q3.e7_pareto import dominates
OUT=ROOT/'results/xb1'
def read(p):return json.loads(p.read_text())
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    source=read(OUT/'source/manifest.json')
    for r in source['files']:assert digest(OUT/'source'/r['file'])==r['sha256']
    for p,h in read(OUT/'local_input_manifest.json').items():assert digest(ROOT/p)==h
    for p,h in read(ROOT/'results/q3/e8/frozen_input_manifest.json')['hashes'].items():assert digest(ROOT/p)==h
    q2=read(OUT/'validation.json');assert q2['gate']=='XB1_Q2_EXTERNAL_STRUCTURES_VERIFIED'
    for pid in ['XB01','XB02']:
        p=ROOT/'results/q2/pareto_schedules'/pid;r=read(p/'validation.json')
        assert r['status']=='XB1_Q2_INDEPENDENTLY_VALIDATED' and r['J_late']==0
        for f,h in r['artifact_sha256'].items():assert digest(p/f)==h,(pid,f)
    total=0;fine=0
    for pid in ['XB01','XB02']:
        base=OUT/'q3'/pid
        for p,h in read(base/'cache_input_manifest.json').items():assert digest(ROOT/p)==h
        coarse=read(base/'validation_0.5.json');refined=read(base/'validation_0.25.json')
        assert coarse['status']==refined['status']=='XB1_Q3_INDEPENDENTLY_VALIDATED'
        for r in coarse['solutions']+refined['solutions']:
            assert r['status']=='XB1_Q3_INDEPENDENTLY_VALIDATED' and r['uncovered_sample_count']==0
            assert r['hard_deadline_violations']==0
            for p,h in r['artifact_sha256'].items():assert digest(ROOT/p)==h,p
        assert len(refined['solutions'])==1;fine+=1;total+=len(coarse['solutions'])
        status=dict(status='XB1_Q3_INDEPENDENTLY_VALIDATED',solutions=len(coarse['solutions']),fine_representatives=1,Gamma_C_db=0)
        (base/'status.json').write_text(json.dumps(status,indent=2)+'\n')
    assert total==9 and fine==2
    dem=read(OUT/'exact_geometry_validation.json');assert dem['legs']==240
    exact=read(OUT/'dem_sensitivity_summary.json');assert len(exact)==5 and all(r['status']=='XB1_Q2_INDEPENDENTLY_VALIDATED' for r in exact)
    for p in (OUT/'dem_sensitivity/q2/pareto_schedules').glob('*/validation.json'):
        for f,h in read(p)['artifact_sha256'].items():assert digest(p.parent/f)==h
    replay=read(OUT/'replay_checks.json');assert len(replay)==11 and all(r['byte_identical'] and all(r['files'].values()) for r in replay)
    comp=pd.read_csv(OUT/'dominance_checks.csv');assert comp[comp.question=='Q2'].dominates.all()
    selected=comp[(comp.question=='Q3')&(comp.candidate=='XB01_Q3_001')];assert len(selected)==8 and selected.dominates.all()
    front=pd.read_csv(OUT/'q3_frontier.csv').to_dict('records')
    assert all(not dominates(a,b) for i,a in enumerate(front) for j,b in enumerate(front) if i!=j)
    tests=read(OUT/'regression_checks.json');assert tests['tests_run']==6 and tests['failures']==0 and tests['errors']==0
    files=[p for p in OUT.rglob('*') if p.is_file() and p.suffix!='.log' and p.name!='gate.json' and 'test_work' not in p.parts and 'replay_work' not in p.parts]
    for pid in ['XB01','XB02']:files+=list((ROOT/'results/q2/pareto_schedules'/pid).glob('*'))
    files+=list((ROOT/'src/xb1').glob('*.py'))+list((ROOT/'validation/mathematical').glob('*xb1*.py'))
    files += [ROOT/p for p in ['src/q2/initial_solution.py','src/q2/operators.py','results/project_status.json','README.md','docs/paper/MAIN_RESULTS_FREEZE_20260925.md']]
    result=dict(gate='XB1_EXTERNAL_BENCHMARK_AND_Q3_CLOSED',external_repository=source['repository'],external_commit=source['commit'],Q2_verified=2,Q3_verified=9,Q3_fine_representatives=2,replay_packages=11,regression_tests=6,old_Q2_all_dominated=True,old_E7_all_dominated_by='XB01_Q3_001',recommended_Q3='XB01_Q3_001',Gamma_C_db=0,external_structure_attribution_required=True,exact_dem_Q2_sensitivity_verified=True,exact_dem_Q3_rebuilt=False,Q4='OLD_BASELINE_ONLY_REBASE_REQUIRED',E8='OLD_P01_STRUCTURE_ONLY',legacy_frozen_inputs_unchanged=True,global_optimum_proven=False,output_sha256={str(p.relative_to(ROOT)):digest(p) for p in sorted(set(files))})
    (OUT/'gate.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='output_sha256'},indent=2))
if __name__=='__main__':main()
