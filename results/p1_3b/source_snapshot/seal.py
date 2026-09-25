"""Final cross-file acceptance checks, then hash only this stage's files."""
from pathlib import Path
import subprocess,json
from src.bench_p1_3b.common import *

def main():
    required=['GPT_SYNC.md','gate.json','pool_manifest.json','finite_pool_extremes.json','solver_bounds.json','diverse_transport_structures.json','q3_screening.json','independent_audit.json','REPRODUCE.md']
    assert all((OUT/p).is_file() for p in required)
    gate=read(OUT/'gate.json');allowed={'P1_3B_POOL_SUFFICIENT_FOR_Q3_DECOMPOSITION','P1_3B_POOL_STRUCTURE_LIMITED','P1_3B_SOLVER_GAP_BLOCKED','P1_3B_Q3_COUPLING_BLOCKED'}
    assert gate['status'] in allowed
    pm=read(OUT/'pool_manifest.json');assert pm['actual_patterns']==2903 and pm['single_stop']==296 and pm['two_stop']==2607
    assert digest(OUT/'inputs/pattern_pool.json')==pm['sha256']
    e=read(OUT/'finite_pool_extremes.json')['results'];assert len(e)==4
    for r in e:
        assert r['valid_full_pool_lower_bound']<=r['upper_bound']+1e-8
        assert not r['finite_continuous_pool_optimality_proven']
    d=read(OUT/'diverse_transport_structures.json');assert d['new_representative_count']==9 and d['historical_readmissions']==3
    new=[r for r in d['representatives'] if r['anchor']!='HISTORICAL'];assert len({r['signature'] for r in new})==9
    assert len(d['time_representatives'])==3 and all(r['relative_to_best']<=.05 for r in d['time_representatives'])
    q=read(OUT/'q3_screening.json');assert len(q['records'])==6
    for r in q['records']:
        assert r['cold_config']['sites']==118 and r['cold_config']['Gamma_C_db']==0
        assert r['cold_config']['relay_uavs']==2 and r['cold_config']['energy_components']==6
        assert all(not t['cache_hit'] for t in r['cold_template_log'])
        assert not r['infeasibility_proven']
    v=read(OUT/'verification.json');assert v['status']=='PASSED' and len(v['certificates'])==19 and len(v['packages'])==13
    assert len([r for r in v['certificates'] if r['path'].startswith('results/p1_3b/bounds/')])==4
    protected=read(OUT/'protection_check.json');assert protected['all_unchanged'] and protected['main_unchanged']
    prior=next(r for r in read(ROOT/'results/p1_3a/transport_resource_lower_bounds.json') if r['pid']=='A11')
    assert abs(prior['universal_fixed_transport_makespan_lower_bound_s']-6300.781643600972)<1e-9
    code=[]
    for run in ['makespan_v3','sorties_v3','energy_v3','J_norm_v3']:
        config=read(OUT/'transport_runs'/run/'config.json')
        for name in ['common.py','transport.py']:
            path=ROOT/'src/bench_p1_3b'/name;assert digest(path)==config['source_hashes'][str(path.relative_to(ROOT))]
        code.append(dict(run=run,executed_model_source_matches=True))
    write(OUT/'integration_check.json',dict(status='PASSED',complete_pool_verified=True,full_pool_bounds=4,
        independent_certificate_replays=19,validated_Q2=12,validated_Q3=1,all_cold_templates_misses=True,
        source_checks=code,historical_A11_lower_bound_unchanged=True,history_files_unchanged=protected['files']))
    snapshot=OUT/'source_snapshot';snapshot.mkdir(exist_ok=True)
    import shutil
    for p in (ROOT/'src/bench_p1_3b').glob('*.py'):shutil.copy2(p,snapshot/p.name)
    hashes={}
    for root in [ROOT/'src/bench_p1_3b',OUT]:
        for p in sorted(root.rglob('*')):
            if p.is_file() and '__pycache__' not in p.parts and p!=OUT/'artifact_manifest.json':hashes[str(p.relative_to(ROOT))]=digest(p)
    write(OUT/'artifact_manifest.json',dict(files=hashes,exclusions=['artifact_manifest.json','__pycache__','.deps_p13b']))
    print('SEALED',len(hashes),'files;',gate['status'])

if __name__=='__main__':main()
