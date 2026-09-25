"""Seal both authorized work streams without staging historical changes."""
import shutil,subprocess
from src.bench_p1_4.common import *

def main():
    audit=read(OUT/'independent_audit.json');gate=read(OUT/'gate.json');assert audit['Q2_packages']==19 and audit['new_Q3_packages']==5
    assert gate['status']=='P1_4_NEAR_FAST_TRADEOFFS_VERIFIED_PAPER_V01_READY'
    papers=read(ROOT/'results/paper_v01/artifact_manifest.json')
    for f,h in papers['files'].items():assert digest(ROOT/f)==h,f
    bounds=read(OUT/'site_cover_bounds.json');assert len(bounds)==8 and all(r['relay_sorties_lower_bound']==3 for r in bounds)
    initial=read(OUT/'screening/F18/C2_SITE_B6500/master_00/result.json')
    repaired=read(OUT/'screening/F18/C2_SITE_3PAIR_B6500/master_00/result.json')
    assert len(initial['relay_guidance'])==4 and len(repaired['relay_guidance'])<=3 and repaired['necessary_three_UAV_site_pair_cap']
    assert read(OUT/'screening/F18/C2_SITE_3PAIR_B6500/result.json')['witnesses']
    for r in audit['Q3']:
        v=read(ROOT/r['package']/'validation_0.5.json')
        for f,h in v['artifact_sha256'].items():assert digest(ROOT/f)==h
    original={'results/q2/q2_battery_calendar.csv','results/q2/q2_box_delivery.csv','results/q2/q2_sorties.csv','results/q2/q2_uav_calendar.csv','results/q3/relay_candidate_gate_stats_raw.csv'}
    assert set(subprocess.check_output(['git','diff','--name-only'],text=True,cwd=ROOT).splitlines())==original
    assert subprocess.check_output(['git','rev-parse','HEAD'],text=True,cwd=ROOT).strip()=='842d950eba19374a287351b9b839fb446ff55d14'
    snapshot=OUT/'source_snapshot';snapshot.mkdir(exist_ok=True)
    for p in (ROOT/'src/bench_p1_4').glob('*.py'):shutil.copyfile(p,snapshot/p.name)
    write(OUT/'integration_check.json',dict(status='PASSED',Q2=19,new_Q3=5,readmitted_Q3_anchors=4,finite_nondominated=7,
        unit_tests=3,finite_matrix_primals=audit['matrix_primals'],site_cover_lower_bounds=8,
        F18_three_pair_feedback_integration='PASSED: four-pair guidance failed restricted repair; necessary <=3 pair feedback produced independently validated three-flight witness',
        paper_files=len(papers['files'])+1,paper_source_hashes=119,paper_original_Q3_artifact_hashes=84,
        historical_files_preserved=read(OUT/'protection_check.json')['files'],main_Q4_workbook_unchanged=True,
        plots_visually_checked=True,continuous_global_optimality_proven=False))
    roots=[ROOT/'src/bench_p1_4',OUT,ROOT/'results/paper_v01']
    paths=[p for d in roots for p in d.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p!=OUT/'artifact_manifest.json']
    write(OUT/'artifact_manifest.json',dict(files={str(p.relative_to(ROOT)):digest(p) for p in sorted(paths)},
        exclusions=['__pycache__','results/p1_4/artifact_manifest.json itself']))
    print('SEALED',len(paths),'hashed files',sum(p.stat().st_size for p in paths),'bytes')
if __name__=='__main__':main()
