"""Explicitly admit the user-requested autonomous comparison records."""
from pathlib import Path
from collections import Counter
import json,hashlib
import pandas as pd
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'results/p1_5b'
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
def main():
    old=read(ROOT/'results/p1_5a/PAPER_SOURCE_WHITELIST.json')
    for e in old['sources']:assert sha(ROOT/e['path'])==e['sha256'],e['path']
    pool=read(ROOT/'results/p1_3b/inputs/pattern_pool.json')
    boxclass={b:i for i,c in enumerate(pool['classes']) for b in c['boxes']}
    lookup={(r['type'],tuple(r['sequence']),tuple(map(tuple,r['counts']))):i for i,r in enumerate(pool['patterns'])}
    added=[];comparators=[]
    for pid in ['F12','F16','F13','F18','C01']:
        if pid=='F13':
            package=ROOT/'results/p1_5a/execution/q3/F13/solutions/F13_C2_SITE_B6500_RELAY_00_Q3'
            base=ROOT/'results/p1_5a/execution/q2/pareto_schedules/F13'
        elif pid=='C01':
            package=ROOT/'results/p1_3b/screening/C01/q3/C01/solutions/C01_Q3_001'
            base=ROOT/'results/p1_3b/q2/pareto_schedules/C01'
        else:
            directory=ROOT/f'results/p1_4/screening/{pid}/q3/{pid}/solutions'
            pp=list(directory.iterdir());assert len(pp)==1;package=pp[0]
            base=ROOT/f'results/p1_4/screening/{pid}/q2/pareto_schedules/{pid}'
        validation=read(package/'validation_0.5.json')
        assert validation['hard_violations']==validation['uncovered_sample_count']==validation['J_late']==0
        for rel,h in validation['artifact_sha256'].items():
            assert sha(ROOT/rel)==h,rel
            added.append(ROOT/rel)
        missions=read(base/'missions.json');indices=[]
        for m in missions:
            key=(m['uav_type'],tuple(m['service_sequence']),tuple(sorted(Counter(boxclass[b] for b in m['box_ids']).items())))
            indices.append(lookup[key])
        assert len(indices)==len(missions)
        m=read(package/f'joint_metrics_{pid}.json')
        assert m['Gamma_C_db']==0
        added += [package/'validation_0.5.json',base/'missions.json',package/f'joint_metrics_{pid}.json']
        comparators.append(dict(id=pid,metrics={k:m[k] for k in ['J_late','J_norm','joint_makespan_s','total_energy_kwh','transport_energy_kwh','relay_energy_kwh','transport_sorties','relay_sorties']},
            package=str(package.relative_to(ROOT)),validation_hash=sha(package/'validation_0.5.json'),pattern_indices=indices,
            admission='Original independent validation artifact hashes + autonomous pool membership checked; no new search and no claim of re-running full radio audit'))
    write(OUT/'admitted_comparators.json',comparators)
    # Fixed-structure workload bound is safe across schedules; no grid bound is transferred.
    rep=read(ROOT/'results/p1_4/representatives/F13.json')
    t=pd.read_csv(ROOT/'results/p1_5a/execution/q3/F13/solutions/F13_C2_SITE_B6500_RELAY_00_Q3/transport_sorties_F13.csv')
    bound=dict(lower_s=rep['transport_workload_lower_bound_s'],upper_transport_s=float(t.return_s.max()),
        upper_joint_s=next(x['metrics']['joint_makespan_s'] for x in comparators if x['id']=='F13'),
        scope='Only the fixed F13 box/visit/type structure; transport occupation lower bound also lower-bounds joint makespan; no all-structure optimum claim')
    assert bound['lower_s']<=bound['upper_transport_s']+1e-8<=bound['upper_joint_s']+1e-8
    write(OUT/'fixed_structure_bound.json',bound)
    write(OUT/'admission.json',dict(status='PASSED',authorization='User-requested F12/F16/F13/F18 local tradeoff plus autonomous low-resource representative in prior draft',
        inherited_whitelist_sha256=sha(ROOT/'results/p1_5a/PAPER_SOURCE_WHITELIST.json'),
        added_sources={str(p.relative_to(ROOT)):sha(p) for p in sorted(set(added))},
        full_radio_rerun=False,external_result_sources_read=False))
    print('ADMITTED',[(x['id'],x['metrics']['transport_sorties']) for x in comparators],bound,flush=True)
if __name__=='__main__':main()
