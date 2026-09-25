"""Cold Q3 feasibility screen of a few independently validated pool structures."""
import argparse,copy,shutil,time,warnings
import numpy as np
from fractions import Fraction
from scipy.optimize import linprog
from src.bench_p1_3b.common import *
from src.bench_p1 import q3_adapter as adapter
from src.bench_p1 import joint_kernel
from src.bench_p1_2.driver import audit
from src.q3.e8_seed_variants import partition
from src.bench_p1_3a.model import LinearModel,lp_form,rational_lagrangian_bound

def count_bound(e,proposals,root):
    """Valid count bound only within the declared cold group catalogue."""
    groups={tuple(g['task_ids']) for row in proposals for g in row['groups']}
    groups.update((a,) for a in e.atoms.index);groups=sorted(groups);eligible=[]
    for ids in groups:
        longest=max(float(e.atoms.loc[a].service_duration_s) for a in ids)
        sites=[s for s in sorted(e.common(ids)) if e.energy(e.sites[s],0)['total_energy_kwh']+(e.pr['hover_power_kw']+e.pr['comm_power_kw'])*longest/3600<=(1-e.pr['rho'])*e.pr['energy_kwh']+1e-10]
        if sites:eligible.append(dict(tasks=ids,sites=sites))
    m=LinearModel();z=[m.var(f'group_{i}',0,1,integer=True) for i in range(len(eligible))]
    for aid in e.atoms.index:m.eq({z[i]:1 for i,g in enumerate(eligible) if aid in g['tasks']},1,'COVER_EACH_ATOM_ONCE')
    a,lo,hi=m.arrays();c=np.ones(len(z));au,bu,ae,be,um,em=lp_form(a,lo,hi);d=root/'relay_count_bound';d.mkdir()
    write(d/'catalogue.json',eligible);np.savez_compressed(d/'model.npz',data=a.data,indices=a.indices,indptr=a.indptr,shape=a.shape,lower=lo,upper=hi,lb=m.lb,ub=m.ub,integrality=m.integer,objective=c)
    tick=time.process_time();lp=linprog(c,A_eq=ae,b_eq=be,bounds=list(zip(m.lb,m.ub)),method='highs',options=dict(threads=1,time_limit=30));cpu=time.process_time()-tick
    result=dict(scope='FINITE_COLD_GROUP_CATALOGUE_COUNT_RELAXATION; ignores timing, energy overlaps and all resources',
        groups=len(eligible),status=int(lp.status),message=str(lp.message),cpu_s=cpu,iterations=int(lp.nit),nodes=None,
        full_Q3_lower_bound=False,finite_group_catalogue_only=True)
    if lp.success:
        cert=rational_lagrangian_bound(c,a,lo,hi,m.lb,m.ub,um,em,[],lp.eqlin.marginals);cert['matrix_sha256']=digest(d/'model.npz');write(d/'certificate.json',cert)
        result.update(lower_bound=math.ceil(Fraction(int(cert['numerator']),int(cert['denominator']))),bound_status='VALID_FOR_DECLARED_COLD_GROUP_CATALOGUE_ONLY')
    else:result.update(lower_bound=None,bound_status='BOUND_NOT_VALID')
    write(d/'result.json',result);return result

def main():
    ap=argparse.ArgumentParser();ap.add_argument('pid');ap.add_argument('--limit',type=float,default=30);args=ap.parse_args();pid=args.pid
    install_input_guard();warnings.filterwarnings('ignore',message='Unrecognized options detected')
    root=OUT/'screening'/pid
    if root.exists():raise RuntimeError('Refuse overwrite '+str(root))
    root.mkdir(parents=True);tick=time.process_time();rep=read(OUT/'representatives'/f'{pid}.json');src=ROOT/rep['package']
    assert digest(src/'validation.json')==rep['validation_sha256']
    shutil.copytree(src,root/'q2/pareto_schedules'/pid)
    e=adapter.Engine(root,pid,lambda stage:print(pid,stage,flush=True));e.pool();assert len(e.sites)==118
    adapter.core.RESULTS_Q2=root/'q2';adapter.shift.RESULTS_Q2=root/'q2';adapter.exporter.RESULTS_Q2=root/'q2'
    config=dict(pid=pid,transport_structure=rep['signature'],Gamma_C_db=0,sites=118,relay_uavs=2,energy_components=6,solver_seed=26092511,solver_threads=1,
        cold_tasks_and_pairs=True,historical_pair_cache_used=False,mip_limit_per_partition_s=args.limit,
        partition_batches=[6,8,12],source='Entire autonomous 2903 pattern pool',
        seed_model_scope='Fixed proposed task groups/sites; free transport shifts and typed resource orders; conservative span-based relay energy only in seed MILP, original union energy in execution validation',
        rejection_does_not_prove_Q3_infeasibility=True)
    write(root/'config.json',config)
    unresolved=[a for a in e.atoms.index if not e.common([a])]
    if unresolved:
        write(root/'result.json',dict(pid=pid,status='NO_LINK_COVER_IN_FROZEN_COORDINATES',unresolved=unresolved,infeasibility_proven=False,total_cpu_s=time.process_time()-tick));return
    order=list(adapter.read(e.base/'q2_sorties.csv').sort_values(['preparation_start_s','sortie_id']).sortie_id);proposals=[]
    for batch in [6,8,12]:
        groups=[]
        for start in range(0,len(order),batch):
            ids=list(e.atoms[e.atoms.transport_sortie_id.isin(order[start:start+batch])].atomic_task_id)
            if ids:groups+=partition(e,ids,'unit')
        proposals.append(dict(batch=batch,groups=groups))
    write(root/'proposals.json',proposals);bound=count_bound(e,proposals,root)
    class Timing(adapter.core.Timing):
        def __init__(self,engine,_pid,groups):super().__init__(engine,pid,groups,objective='makespan',late_budget=0.)
    from scipy.optimize import milp as original_milp
    def seeded_milp(*aa,**kw):
        kw['options']=dict(kw.get('options',{}),threads=1,random_seed=26092511)
        return original_milp(*aa,**kw)
    joint_kernel.milp=seeded_milp
    joint_kernel.Timing=Timing;attempts=[];accepted=[]
    for proposal in sorted(proposals,key=lambda r:(len(r['groups']),r['batch'])):
        start=time.process_time()
        try:
            answer,info=joint_kernel.relay_order_milp(e,proposal['groups'],limit=args.limit,joint_resources=True)
            row=dict(batch=proposal['batch'],groups=len(proposal['groups']),raw_solver=info,cpu_s=time.process_time()-start,
                raw_dual_scope='Conservative fixed-group seed MILP objective is lateness, NOT a full-Q3 count or energy lower bound')
            if answer and answer['metrics']['J_late']<=1e-4:
                ident=pid+'_Q3_001';adapter.export_local(e,copy.deepcopy(answer),ident);package=e.dest/'solutions'/ident
                mm=read(package/f'joint_metrics_{pid}.json');mm.update(source_provenance='P1_3B_AUTONOMOUS_POOL',global_optimum_proven=False);write(package/f'joint_metrics_{pid}.json',mm)
                validation=audit(root,pid,package)
                assert validation['J_late']<=1e-4 and validation['hard_violations']==0 and validation['uncovered_sample_count']==0
                accepted.append(dict(id=ident,metrics=answer['metrics'],package=str(package.relative_to(ROOT)),validation=validation,
                    validation_sha256=digest(package/'validation_0.5.json')))
                row['outcome']='INDEPENDENTLY_VALIDATED_ZERO_LATE_LAYER'
            else:row['outcome']='NO_ZERO_LATE_WITNESS';row['candidate_metrics']=None if answer is None else answer['metrics']
        except Exception as exc:
            row=dict(batch=proposal['batch'],status='ERROR_RETAINED',error=repr(exc),cpu_s=time.process_time()-start)
        attempts.append(row);write(root/'attempts.json',attempts);print('Q3_ATTEMPT',pid,row['batch'],row.get('outcome',row.get('error')),flush=True)
        if accepted:break
    write(root/'result.json',dict(pid=pid,status='Q3_ZERO_LATE_WITNESS_INDEPENDENTLY_VALIDATED' if accepted else 'NO_WITNESS_IN_BOUNDED_COLD_SCREEN',
        witnesses=accepted,relay_count_bound=bound,attempts=len(attempts),infeasibility_proven=False,total_cpu_s=time.process_time()-tick))

if __name__=='__main__':main()
