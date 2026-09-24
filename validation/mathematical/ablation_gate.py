"""Independent equal-CPU benchmark accounting and G2 result-preservation gate."""
import hashlib,json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'results/ablation180_v2'
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):return json.loads(p.read_text())
def check_budget(run,checkpoints,protocol):
    cap=protocol['cpu_budget_s'];tol=protocol['maximum_observed_cpu_overshoot_tolerance_s']
    if run['termination'] not in ['CPU_BUDGET','WORKER_FINISHED'] or run['exit_code'] not in [0,-9]:raise ValueError('Unexpected termination invalidates CPU comparison')
    if run['observed_process_cpu_s']>cap+tol:raise ValueError('CPU cap exceeded')
    expected={r['pid'] for r in checkpoints if r['cpu_ready_s']<=cap}
    if set(run['accepted_checkpoints'])!=expected:raise ValueError('Accepted checkpoint set differs from CPU cutoff')
    if len({r['pid'] for r in checkpoints})!=len(checkpoints):raise ValueError('Duplicate checkpoint identity')
def main():
    protocol=load(OUT/'protocol.json');assert protocol['version']=='CPU180_FIVE_SEEDS_Q2_V2' and protocol['cpu_budget_s']==180
    runs=load(OUT/'run_status.json');expected={f'{method}_{seed}' for method in protocol['methods'] for seed in protocol['seeds']};assert len(runs)==15 and {r['run'] for r in runs}==expected
    for name,h in protocol['source_hashes'].items():assert digest(ROOT/name)==h,('Protocol code changed',name)
    total=0;maxcpu=0.;physicalcores={(x['physical id'],x['core id']) for x in protocol['cpu_topology'] if int(x['processor']) in protocol['cores']};assert len(physicalcores)==3
    for run in runs:
        d=OUT/run['run'];rows=load(d/'checkpoints.json');check_budget(run,rows,protocol);cfg=load(d/'config.json')
        assert cfg['cpu_budget_s']==180 and cfg['core']==run['core'] and cfg['threads']==1
        maxcpu=max(maxcpu,run['observed_process_cpu_s'])
        for pid in run['accepted_checkpoints']:
            p=d/'q2/pareto_schedules'/pid;a=load(p/'validation.json');assert a['status']=='XB1_Q2_INDEPENDENTLY_VALIDATED'
            for name,h in a['artifact_sha256'].items():assert digest(p/name)==h,('Checkpoint modified after audit',p,name)
            total+=1
    assert not load(OUT/'audit_failures.json')
    wins=load(OUT/'verified_challenge_wins.json');method_summary=load(OUT/'method_summary.json')
    for method in method_summary:assert method['verified_dominance_wins']==sum(w['run'].rsplit('_',1)[0]==method['method'] for w in wins)
    calibration=load(OUT/'cpu_clock_calibration.json');assert calibration['status']=='PARENT_CHILD_PROCESS_CPU_CLOCK_MATCH' and calibration['max_abs_read_lag_cpu_s']<.05
    paired=load(OUT/'paired_pool_checks.json');assert len(paired)==5 and all(x['identical_generated_pool'] for x in paired),'Paired pool definitions differ'
    assert load(ROOT/'results/ablation180/timing_invalid.json')['all_runs_excluded_from_formal_comparison']
    # Historical G2 authority is bound to its original revision. Mutable landing
    # documents are verified there; all mathematical artifacts must remain exact.
    old=load(ROOT/'results/reset/gate.json');revision='4ae3d2d0d584d648c814e1b7c2d98613237a920e';mutable={'README.md','results/project_status.json'}
    for name,h in old['artifact_sha256'].items():
        if name in mutable:
            blob=subprocess.check_output(['git','show',revision+':'+name],cwd=ROOT);assert hashlib.sha256(blob).hexdigest()==h
        else:assert digest(ROOT/name)==h,('Frozen G2 mathematical evidence changed',name)
    sub=load(ROOT/'results/reset/submission/validation.json');assert digest(ROOT/'results/reset/submission/结果提交表_G2_自主主方案.xlsx')==sub['workbook_sha256']
    tests=(OUT/'regression_tests.log').read_text();assert '\nOK\n' in tests and 'FAILED' not in tests
    result=dict(gate='G2_MAIN_PRESERVED_Q2_EQUAL_CPU_FIVE_SEEDS_VERIFIED',benchmark_scope='Q2_ONLY_THREE_SPECIFIC_IMPLEMENTATIONS_ONE_INSTANCE',runs=15,seeds_per_method=5,cpu_budget_s=180,maximum_observed_cpu_s=maxcpu,verified_in_budget_checkpoints=total,strict_equal_cpu_multiseed_comparison_completed=True,equal_budget_means='same enforced CPU cap, not identical consumption or machine instructions',Q3_multiseed_algorithm_comparison_completed=False,Q3_main='A11_Q3_001',G2_original_gate=old['gate'],G2_original_revision=revision,G2_mathematical_outputs_byte_preserved=True,combined_submission_byte_preserved=True,invalid_v1_excluded=True,global_pareto_proven=False,new_Q2_verified_dominance_wins=len(load(OUT/'verified_challenge_wins.json')),Q3_existing_verified_dominance_wins=7,algorithm_expansion='STOP_AFTER_THIS_EXPERIMENT',paper_status='MAIN_TEXT_DRAFT_WITH_VERIFIED_RESULTS_NOT_FINAL_FORMATTED_SUBMISSION')
    files=[p for p in OUT.rglob('*') if p.is_file() and p!=OUT/'gate.json' and 'partial' not in p.parts and not p.name.endswith('.tmp')]
    files += list((ROOT/'src/bench').glob('*.py'))+[Path(__file__),ROOT/'validation/mathematical/test_ablation_accounting.py',ROOT/'docs/paper/G2_PAPER_MAIN_DRAFT.md',ROOT/'docs/paper/G2_EVIDENCE_MAP.md',ROOT/'README.md',ROOT/'results/project_status.json']
    result['artifact_sha256']={str(p.relative_to(ROOT)):digest(p) for p in sorted(set(files))}
    (OUT/'gate.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='artifact_sha256'},indent=2))
if __name__=='__main__':main()
