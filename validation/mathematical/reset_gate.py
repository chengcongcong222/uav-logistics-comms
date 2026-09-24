"""G2 evidence gate: verify stored independent checks and immutable input hashes."""
import hashlib,json,sys
from pathlib import Path
import pandas as pd
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT));OUT=ROOT/'results/reset'
from src.q3.e7_pareto import dominates
def load(p):return json.loads(p.read_text())
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def check_hashes(hashes,base=ROOT):
    for name,value in hashes.items():assert digest(base/name)==value,('STALE_EVIDENCE',name)
def main():
    assert load(OUT/'supplied_witness_audit.json')['status']=='THREE_SUPPLIED_Q2_WITNESSES_CROSS_VALIDATED'
    geo=load(OUT/'geometry/validation.json');assert geo['directed_legs']==240 and geo['status']=='G2_NATIVE_CELL_GEOMETRY_INDEPENDENTLY_VALIDATED'
    check_hashes(load(OUT/'geometry/manifest.json')['hashes'])
    for p in (ROOT/'data/processed').glob('*'):
        if p.is_file() and p.name!='route_geometry.csv':assert digest(p)==digest(OUT/'geometry'/p.name),('INPUT_TABLE_MISMATCH',p.name)
    assert load(OUT/'q1/validation.json')['status']=='G2_Q1_INDEPENDENT_PHYSICS_VERIFIED'
    q2=[];q3=[];byid={}
    for p in sorted((OUT/'q2/pareto_schedules').iterdir()):
        if (p/'template_status.json').exists():continue
        audit=load(p/'validation.json');assert audit['status']=='XB1_Q2_INDEPENDENTLY_VALIDATED';check_hashes(audit['artifact_sha256'],p);q2.append(p.name)
    for p in sorted((OUT/'q3').glob('*/solutions/*')):
        a=load(p/'validation_0.5.json');assert a['status']=='G2_Q3_INDEPENDENTLY_VALIDATED' and a['uncovered_sample_count']==0 and a['hard_violations']==0
        check_hashes(a['artifact_sha256']);check_hashes(load(p/'input_manifest.json')['hashes']);q3.append(p.name);m=load(p/'witness.json')['metrics'];byid[p.name]=m
        pid=p.parent.parent.name;t=pd.read_csv(p/f'transport_sorties_{pid}.csv');r=pd.read_csv(p/f'relay_sorties_{pid}.csv')
        for k in ['J_late','J_norm','transport_energy_kwh','transport_sorties']:assert abs(m[k]-a[k])<1e-5,(p.name,k)
        assert abs(m['joint_makespan_s']-max(t.return_s.max(),r.return_s.max()))<1e-6
        assert abs(m['total_energy_kwh']-t.energy_kwh.sum()-r.total_energy_kwh.sum())<1e-7
        assert m['relay_sorties']==len(r)
    fine=[]
    for pid,sid in [('A11','A11_Q3_001'),('B01','B01_Q3_002_CC')]:
        p=OUT/'q3'/pid/'solutions'/sid;a=load(p/'validation_0.25.json');assert a['status']=='G2_Q3_INDEPENDENTLY_VALIDATED' and a['uncovered_sample_count']==0;check_hashes(a['artifact_sha256']);fine.append(sid)
    q4=load(OUT/'q4/validation.json');assert q4['source_solution']=='A11_Q3_001' and q4['enumerated_partitions']=={'2':31,'3':90};check_hashes(q4['artifact_sha256']);check_hashes(load(OUT/'q4/input_manifest.json')['hashes'])
    sub=load(OUT/'submission/validation.json');assert sub['status']=='G2_SUBMISSION_INDEPENDENTLY_VERIFIED';assert digest(OUT/'submission/结果提交表_G2_自主主方案.xlsx')==sub['workbook_sha256'];check_hashes(load(OUT/'submission/input_manifest.json')['hashes'])
    challenges=load(OUT/'contained_cell_challenges.json');winners=[]
    for r in challenges:
        for a in r['attempts']:
            if a['branch']=='equal_lateness':assert a['original_in_linear_domain']
        if 'challenger' in r:
            assert dominates(byid[r['challenger']],byid[r['source']]);winners.append([r['source'],r['challenger']])
    assert len(winners)==7
    for f in ['regressions.log','xb1_regressions.log']:
        text=(OUT/f).read_text();assert '\nOK\n' in text and 'FAILED' not in text
    fronts=load(OUT/'archive_frontiers.json')['frontiers']
    for name in ['Q3_OWN_GENERATED','Q3_EXTERNAL_CONTROL','Q3_COMBINED']:
        assert set(fronts[name])<=set(q3)
        rr=[byid[s] for s in fronts[name]];assert not any(i!=j and dominates(a,b) for i,a in enumerate(rr) for j,b in enumerate(rr))
    result=dict(gate='G2_AUTONOMOUS_MAIN_Q1_Q4_SUBMISSION_VERIFIED',geometry=load(OUT/'geometry/config.json')['version'],Q2_verified=q2,Q3_verified=q3,Q3_verified_count=len(q3),Q3_fine_representatives=fine,Q3_main='A11_Q3_001',Q4_source='A11_Q3_001',Q4_inventory_sufficient=False,submission_verified=True,source_lines_separate=True,archive_frontiers=fronts,active_dominance_counterexamples=winners,global_pareto_proven=False,restricted_nondominance_proven=False,strict_equal_cpu_multiseed_comparison_completed=False,synchronous_structure_reconstruction_performance_advantage_proven=False,current_main_Gamma_C_cert_db=0,old_Gamma_cert_4_scope='HISTORICAL_P01_ONLY',historical_authority_commit='0025d992816ca40dc9db668e5b120f1c5108c156',Gamma6_and_ns3_new_experiments='STOPPED',regression_tests_passed=14)
    files=[p for p in OUT.rglob('*') if p.is_file() and p!=OUT/'gate.json' and '__pycache__' not in p.parts]
    for directory in ['src/reset','src/common','src/q1','src/q2','src/q3','src/xb1','validation/mathematical']:
        files += list((ROOT/directory).glob('*.py'))
    files += [ROOT/'README.md',ROOT/'results/project_status.json']
    files += [p for p in (ROOT/'data/raw').glob('*') if p.is_file()]
    result['artifact_sha256']={str(p.relative_to(ROOT)):digest(p) for p in sorted(set(files))}
    (OUT/'gate.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='artifact_sha256'},indent=2))
if __name__=='__main__':main()
