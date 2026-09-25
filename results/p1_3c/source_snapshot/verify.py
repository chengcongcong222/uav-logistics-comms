"""Separate evidence replay: raw pair masks, mandatory intervals, sparse primals."""
import itertools,math
import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix
from src.bench_p1_3c.common import *

def site_bound(pid):
    source=ROOT/'results/p1_3b/screening'/pid/'q3'/pid
    tasks=pd.read_csv(source/'guarded_atomic_tasks.csv');pairs=pd.read_csv(source/'candidate_pairs.csv')
    ids=list(tasks.atomic_task_id);masks={}
    for sid,df in pairs.groupby('site_id'):
        mask=sum(1<<ids.index(a) for a in set(df.atomic_task_id));masks[sid]=mask
    unique={}
    for sid,mask in masks.items():unique.setdefault(mask,sid)
    allmask=(1<<len(ids))-1;representatives=list(unique)
    assert not any(m==allmask for m in representatives)
    pairs_checked=0
    for a,b in itertools.combinations_with_replacement(representatives,2):
        assert a|b!=allmask;pairs_checked+=1
    triple=next((x for x in itertools.combinations(representatives,3) if x[0]|x[1]|x[2]==allmask),None)
    assert triple
    return dict(pid=pid,relay_sorties_lower_bound=3,proof='Exhaustive union of every pair of distinct task-coverage masks fails to cover all atoms; each flight uses one site.',
        unique_site_masks=len(unique),two_mask_combinations_checked=pairs_checked,three_site_cover=[unique[v] for v in triple],
        scope='Entire 118-site frozen task-pair relation and unsplit atomic tasks, arbitrary timings/groupings; ignores energy and resources.',
        total_tasks=len(ids),site_masks={s:hex(v) for s,v in masks.items()},inputs={str(p.relative_to(ROOT)):digest(p) for p in [source/'guarded_atomic_tasks.csv',source/'candidate_pairs.csv']})

def replay_conflicts(pid):
    src=ROOT/'results/p1_3b/screening'/pid/'q3'/pid
    atoms=pd.read_csv(src/'guarded_atomic_tasks.csv').set_index('atomic_task_id');pairs=pd.read_csv(src/'candidate_pairs.csv')
    from src.q3.e6_resources import load_relay_params
    pr=load_relay_params();records=[]
    # Independent implementation uses exported flight coefficients, not cut generator.
    covers={a:set(v.site_id) for a,v in pairs.groupby('atomic_task_id')}
    checks=[]
    for directory in [OUT/pid/'C2',OUT/pid/'C2_SITE']:
        if not (directory/'result.json').exists():continue
        result=read(directory/'result.json')
        fixed=read(directory/'fixed_time_conflicts.json')
        sources=[('fixed',c,{s:0. for s in atoms.transport_sortie_id}) for c in fixed]
        for row in result['iterations']:
            sources += [(f"iteration_{row['iteration']}",c,row['master']['shifts']) for c in row.get('new_valid_cuts',[])]
        for label,c,shifts in sources:
            ids=c['tasks'];left=[];right=[]
            for a in ids:
                atom=atoms.loc[a];r=pairs[pairs.atomic_task_id==a]
                left.append(float(atom.service_start_s)+shifts[atom.transport_sortie_id]-float(r.outbound_time_s.min())-pr['prep_time_s']-pr['setup_time_s'])
                right.append(float(atom.service_end_s)+shifts[atom.transport_sortie_id]+float(r.return_time_s.min())+pr['turnaround_time_s'])
            start=max(left);end=min(right);assert start<end-1e-6
            sites=sorted(set().union(*(covers[a] for a in ids)))
            assert not any(all(s in covers[a] or t in covers[a] for a in ids) for s in sites for t in sites)
            assert max(abs(start-c['mandatory_overlap'][0]),abs(end-c['mandatory_overlap'][1]))<1e-6
            checks.append(dict(source=str(directory.relative_to(ROOT)),stage=label,tasks=ids,overlap_s=[start,end],replayed=True))
    return checks

def main():
    install_input_guard();bounds=[];proofs=[];audits=[];matrix_checks=[];transfers=[]
    for pid in ['T01','T02','T03']:
        bounds.append(site_bound(pid));proofs+=replay_conflicts(pid)
        for p in (OUT/pid/'q3'/pid/'solutions').glob('*/validation_0.5.json'):
            v=read(p);assert v['hard_violations']==0 and v['uncovered_sample_count']==0 and v['J_late']<=1e-4
            for f,h in v['artifact_sha256'].items():assert digest(ROOT/f)==h,f
            witness=read(p.parent/'witness.json');source=read(OUT/pid/'q2/pareto_schedules'/pid/'missions.json')
            for stem in ['q2_sorties.csv','missions.json','q2_box_delivery.csv']:
                assert digest(OUT/pid/'q2/pareto_schedules'/pid/stem)==digest(ROOT/'results/p1_3b/screening'/pid/'q2/pareto_schedules'/pid/stem)
            if 'C1_FIXED' in p.parent.name:
                assert all(x==0 for x in witness['shifts'].values())
                f=pd.read_csv(OUT/pid/'q2/pareto_schedules'/pid/'q2_sorties.csv')
                assert all(witness['assignments'][r.sortie_id]==dict(uav_id=r.uav_id,battery_id=r.battery_id) for r in f.itertuples())
            assert len(witness['shifts'])==27 and witness['metrics']['relay_sorties']==3
            audits.append(dict(pid=pid,package=str(p.parent.relative_to(ROOT)),validation_sha256=digest(p),metrics=witness['metrics'],
                fixed_structure_unchanged=True,hashes_checked=len(v['artifact_sha256']),validation=v))
        for p in (OUT/pid).glob('C2_SITE/master_*/result.json'):
            r=read(p);related=[a for a in audits if a['pid']==pid and 'C2_SITE' in a['package']]
            if related:
                physical=related[-1]['metrics']['joint_makespan_s'];raw=r['dual_bound']
                transfers.append(dict(pid=pid,source=str(p.relative_to(ROOT)),encoded_objective_lower_bound=raw,
                    verified_continuous_Q3_makespan=physical,continuous_bound_status='BOUND_NOT_VALID',continuous_Q3_lower_bound=None,
                    reason='Conservative grid/offset master objective is a different quantity. Raw bound exceeds the physical witness; never transfer this bound or gap to continuous Q3.',
                    raw_bound_status='Retained only for its declared encoded model',difference_s=raw-physical))
    for p in OUT.glob('*/C*_*/**/model.npz'):
        file=p.parent/'incumbent.npy'
        if not file.exists():continue
        d=np.load(p);x=np.load(file);a=csr_matrix((d['data'],d['indices'],d['indptr']),shape=tuple(d['shape']));values=a@x
        err=max(0.,float(np.max(d['lower']-values)),float(np.max(values-d['upper'])),float(np.max(-x)),float(np.max(x-1)),float(np.max(abs(x-np.rint(x)))))
        assert err<1e-5,(p,err)
        r=read(p.parent/'result.json');assert abs(d['objective']@x-r['incumbent'])<1e-5
        assert r['dual_bound'] is None or r['dual_bound']<=r['incumbent']+1e-5
        matrix_checks.append(dict(model=str(p.relative_to(ROOT)),maximum_violation=err,incumbent=r['incumbent']))
    write(OUT/'full_site_relay_bounds.json',bounds);write(OUT/'conflict_certificate_replay.json',proofs)
    write(OUT/'bound_transfer_audit.json',transfers);write(OUT/'independent_audit.json',dict(status='PASSED',packages=audits,
        package_count=len(audits),conflict_certificates=len(proofs),matrix_primals=len(matrix_checks),matrix_checks=matrix_checks,
        limitation='Original whole-flight numerical validator: 0.5 s plus phase/gap boundaries and 0.1 s boundary refinement; not an analytic continuous-time radio proof.'))
    print('VERIFIED',len(audits),'packages',len(proofs),'conflict certificates',len(matrix_checks),'matrix primals',flush=True)
if __name__=='__main__':main()
