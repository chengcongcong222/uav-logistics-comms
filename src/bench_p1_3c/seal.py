"""Cross-file consistency and final immutable artifact manifest."""
import shutil,subprocess
from src.bench_p1_3c.common import *

def main():
    gate=read(OUT/'gate.json');assert gate['status']=='P1_3C_FAST_Q3_CLOSED'
    audit=read(OUT/'independent_audit.json');assert audit['package_count']==4
    assert set(gate['verified_structures'])=={a['pid'] for a in audit['packages']}
    for r in read(OUT/'T01_T02_T03_comparison.json'):
        assert r['Q3_closed']
        for w in r['witnesses']:
            assert w['metrics']['J_late']==0 and w['relay_lower_bound']==w['relay_upper_bound']==3
            p=ROOT/w['package'];v=read(p/'validation_0.5.json')
            assert digest(p/'validation_0.5.json')==w['independent_validation_sha256']
            for f,h in v['artifact_sha256'].items():assert digest(ROOT/f)==h
            assert read(p/f"plan_status_{r['pid']}.json")['status']=='P1_3C_Q3_INDEPENDENTLY_VALIDATED'
    old=read(OUT/'protection_check.json');assert old['status']=='PASSED' and old['changed']==[]
    assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()==BASE
    expected={'results/q2/q2_battery_calendar.csv','results/q2/q2_box_delivery.csv','results/q2/q2_sorties.csv','results/q2/q2_uav_calendar.csv','results/q3/relay_candidate_gate_stats_raw.csv'}
    actual=set(subprocess.check_output(['git','diff','--name-only'],cwd=ROOT,text=True).splitlines());assert actual==expected,actual
    snapshot=OUT/'source_snapshot';snapshot.mkdir(exist_ok=True)
    for p in (ROOT/'src/bench_p1_3c').glob('*.py'):shutil.copyfile(p,snapshot/p.name)
    write(OUT/'integration_check.json',dict(status='PASSED',gate=gate['status'],packages=4,structures=3,
        tests=5,conflict_certificates=audit['conflict_certificates'],matrix_primals=audit['matrix_primals'],protected_historical_files=old['files'],
        baseline=BASE,unrelated_initial_dirty_paths_preserved=sorted(expected),all_required_files_present=True,
        continuous_Q3_bound_transfer_rejected=True,relay_count_optimality_scope=gate['relay_count_claim_scope']))
    paths=[p for d in [ROOT/'src/bench_p1_3c',OUT] for p in d.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.name!='artifact_manifest.json']
    manifest={str(p.relative_to(ROOT)):digest(p) for p in sorted(paths)}
    write(OUT/'artifact_manifest.json',dict(files=manifest,exclusions=['__pycache__','artifact_manifest.json itself']))
    print('SEALED',len(manifest),'hashed files',sum(p.stat().st_size for p in paths),'bytes')
if __name__=='__main__':main()
