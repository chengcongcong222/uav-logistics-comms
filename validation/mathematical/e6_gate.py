"""Issue E6 gate only from fresh independent artifact-bound audit results."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'results/q3/e6'


def gate():
    for name,digest in json.loads((OUT/'input_manifest.json').read_text())['hashes'].items():
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest,name
    audits={}
    for pid in ['P01','P02','P03']:
        result=json.loads((OUT/f'validation_{pid}_0.5.json').read_text())
        assert result['status']=='E6_PLAN_INDEPENDENTLY_VALIDATED',pid
        assert result['hard_violations']==result['uncovered_sample_count']==0
        for name,digest in result['artifact_sha256'].items():
            assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest,name
        pool=json.loads((OUT/f'pool_validation_{pid}.json').read_text())
        assert pool['status']=='ALL_RETAINED_EXPANDED_PAIRS_VALIDATED'
        for name,digest in pool['artifact_sha256'].items():
            assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest,name
        audits[pid]=dict(status=result['status'],full_flight_samples=result['full_flight_samples'],
                        expanded_pairs_independently_checked=pool['pairs'])
    sensitive=json.loads((OUT/'validation_P01_0.25.json').read_text())
    assert sensitive['status']=='E6_PLAN_INDEPENDENTLY_VALIDATED'
    for name,digest in sensitive['artifact_sha256'].items():
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest,name
    tests=json.loads((OUT/'regressions.json').read_text());assert tests['failures']==0
    sources=list((ROOT/'src/q3').glob('e6_*.py'))+list((ROOT/'validation/mathematical').glob('e6_*.py'))
    outputs=[p for p in OUT.glob('*') if p.is_file() and p.suffix in ['.json','.csv'] and p.name!='validation.json']
    result=dict(gate='E6_Q3_RELAY_RESOURCE_READY',plans=audits,representative_plan='P01',
                sensitivity_step_s=.25,candidate_set_complete=False,global_optimum_proven=False,
                analytical_continuous_time_proof=False,next_stage_authorized=False,
                output_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in outputs},
                source_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources})
    (OUT/'validation.json').write_text(json.dumps(result,indent=2)+'\n');print(result['gate'])


if __name__=='__main__':gate()
