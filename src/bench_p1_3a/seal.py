"""Check final evidence consistency and seal the stage's artifacts."""
import json
from pathlib import Path
from src.bench_p1.common import ROOT,write,digest

OUT=ROOT/'results/p1_3a'
def read(p):return json.loads(p.read_text())
def main():
    gate=read(OUT/'gate.json');rows=read(OUT/'extreme_results.json')['results']
    assert len(rows)==12
    assert gate['status']=='P1_3A_FINITE_DOMAIN_AUDIT_READY'
    assert read(OUT/'protection_check.json')['all_unchanged']
    certs=read(OUT/'certificate_verification.json')
    assert len(certs['records'])==27 and certs['all_passed']
    for r in rows:
        assert r['bound_status']=='VALID_FOR_DECLARED_FINITE_MILP'
        if r['best_feasible_value'] is not None:
            assert r['accepted_lower_bound']<=r['best_feasible_value']+1e-8
            assert r['incumbent']['metrics']['J_late']<=1e-4
            p=ROOT/r['incumbent']['package']
            assert (p/'witness.json').is_file()
        else:
            assert r['pid']=='A03' and r['verified_incumbent_relative_gap'] is None
    for pid in ('A11','AN01'):
        r=next(r for r in rows if r['pid']==pid and r['anchor']=='relay_sorties')
        assert r['integer_cardinality_optimal_in_declared_catalogue'] and r['accepted_lower_bound']==4
    audit=read(OUT/'independent_audit.json')
    assert audit['hash_bound_p1_2_inputs']==54 and audit['fresh_revalidated_count']==6
    for r in audit['all_revisions_exported_packages']:
        assert r['status']=='P1_Q3_INDEPENDENTLY_VALIDATED' and r['validation_sha256']
    for r in audit['new_solver_candidates']:
        if r['status']=='INDEPENDENTLY_VALIDATED':
            # The unchanged P1.2 adapter returns the original E8 validator
            # tag, then writes the P1 tag to validation_0.5.json (checked above).
            assert r['result']['status']=='E8_PLAN_INDEPENDENTLY_VALIDATED'
            assert r['result']['hard_violations']==0
            assert r['result']['uncovered_sample_count']==0
            assert r['result']['J_late']<=1e-4
    write(OUT/'integration_check.json',dict(status='PASSED',anchor_records=12,certificate_replays=27,
        history_unchanged=True,old_main_unchanged=True,zero_late_incumbents_checked=True,
        catalogue_cardinality_claims_checked=True,new_validation_packages_checked=True))
    hashes={}
    for root in (ROOT/'src/bench_p1_3a',OUT):
        for p in sorted(root.rglob('*')):
            if p.is_file() and '__pycache__' not in p.parts and p!=OUT/'artifact_manifest.json':
                hashes[str(p.relative_to(ROOT))]=digest(p)
    write(OUT/'artifact_manifest.json',dict(files=hashes,exclusions=['artifact_manifest.json','__pycache__']))
    print('INTEGRATION_PASSED; SEALED',len(hashes),'files')

if __name__=='__main__':main()
