"""Hash-bound P1.2 admission, with fresh full audits of representative inputs."""
import json, shutil, subprocess
from pathlib import Path
from src.bench_p1.common import ROOT, write, digest
from src.bench_p1_2.driver import audit

OUT=ROOT/'results/p1_3a'
BASE='dc49b4267c5860d8a6e10728cd629be1009cacc3'
PIDS=('A11','AN01','A03')

def main():
    authority=ROOT/'results/p1_2/artifact_manifest.json'
    assert authority.read_bytes()==subprocess.check_output(['git','show',BASE+':results/p1_2/artifact_manifest.json'],cwd=ROOT)
    hashes=json.loads(authority.read_text())['artifact_sha256']
    sources=[]
    for home in ['warm_readmission','runs/26092511','runs/26092512']:
        for pid in PIDS:
            for p in sorted((ROOT/'results/p1_2'/home/'q3'/pid/'solutions').glob('*/witness.json')):
                package=p.parent
                for f in package.iterdir():
                    if f.is_file():assert digest(f)==hashes[str(f.relative_to(ROOT))]
                validation=json.loads((package/'validation_0.5.json').read_text())
                assert validation['status']=='P1_Q3_INDEPENDENTLY_VALIDATED'
                for f,h in validation['artifact_sha256'].items():assert digest(ROOT/f)==h
                w=json.loads(p.read_text())
                sources.append(dict(id=package.name,pid=pid,package=str(package.relative_to(ROOT)),
                     metrics=w['metrics'],zero_late_eligible=w['metrics']['J_late']<=1e-4,
                     witness_sha256=digest(p),validation_sha256=digest(package/'validation_0.5.json'),
                     admission='HASH_BOUND_PRIOR_FULL_VALIDATION'))
    root=OUT/'admission'
    if root.exists():raise RuntimeError('Refuse overwrite')
    for pid in PIDS:
        src=ROOT/'results/p1_2/runs/26092511/q2/pareto_schedules'/pid
        for p in src.iterdir():
            if p.is_file():assert digest(p)==hashes[str(p.relative_to(ROOT))]
        shutil.copytree(src,root/'q2/pareto_schedules'/pid)
    selected={'A11_Q3_001','D26092511_002','D26092511_005',
              'D26092511_015','AN01_Q3_001_CC','A03_Q3_001'}
    records=[]
    for row in sources:
        if row['id'] not in selected:continue
        dest=root/'q3'/row['pid']/'solutions'/row['id']
        shutil.copytree(ROOT/row['package'],dest)
        try:
            result=audit(root,row['pid'],dest)
            row['admission']='FRESH_FULL_Q3_REVALIDATION'
            records.append(dict(id=row['id'],pid=row['pid'],status='VALIDATED',
                      zero_late_eligible=result['J_late']<=1e-4,result=result))
            print('READMITTED',row['id'],'zero_late',row['zero_late_eligible'],flush=True)
        except Exception as exc:
            records.append(dict(id=row['id'],status='REJECTED',error=repr(exc)))
            write(OUT/'warm_readmission.json',records);raise
        write(OUT/'warm_readmission.json',records)
    write(OUT/'inputs.json',dict(base_commit=BASE,p1_authority_sha256=digest(authority),sources=sources,
        source_scope='AUTONOMOUS_A11_AN01_A03_ONLY',new_transport_box_structures_in_P1_2=0,
        zero_late_counts={pid:sum(r['pid']==pid and r['zero_late_eligible'] for r in sources) for pid in PIDS},
        sources_include_repeated_metric_vectors=True))

if __name__=='__main__':main()
