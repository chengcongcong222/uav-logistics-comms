"""One bounded exact finite-mode rescue after the cold heuristic Q3 screen."""
import argparse,copy,shutil,time,warnings
from fractions import Fraction
import numpy as np
from scipy.optimize import milp,linprog,Bounds,LinearConstraint
from scipy.sparse import csr_matrix,vstack
from src.bench_p1_3b.common import *
from src.bench_p1 import q3_adapter as adapter
from src.bench_p1_2.driver import audit
from src.bench_p1_3a.model import AuditModel,endpoint_mode,lp_form,rational_lagrangian_bound
from src.q3.e8_seed_variants import partition

def main():
    ap=argparse.ArgumentParser();ap.add_argument('pid');ap.add_argument('--limit',type=float,default=90);args=ap.parse_args();pid=args.pid
    install_input_guard();warnings.filterwarnings('ignore',message='Unrecognized options detected')
    prior=OUT/'screening'/pid;root=prior/'exact_rescue'
    if root.exists():raise RuntimeError('Refuse overwrite rescue')
    root.mkdir();tick=time.process_time();shutil.copytree(prior/'q2/pareto_schedules'/pid,root/'q2/pareto_schedules'/pid)
    source=prior/'q3'/pid
    class SavedEngine(adapter.Engine):
        def demands(self,frame):return adapter.read(source/'guarded_atomic_tasks.csv')
    e=SavedEngine(root,pid,lambda stage:print('EXACT',pid,stage,flush=True))
    for row in adapter.read(source/'candidate_pairs.csv').to_dict('records'):
        assert row['site_id'] in e.sites
        e.edges[pid][row['atomic_task_id']][row['site_id']]=row
    write(root/'within_structure_cache_reuse.json',dict(cold_builder=str(prior.relative_to(ROOT)),
        source_hashes={str(f.relative_to(ROOT)):digest(f) for f in [source/'guarded_atomic_tasks.csv',source/'candidate_pairs.csv',source/'candidate_sites.csv']},
        reason='Reuse only this representative own completed cold build; no other structure or historical pairs'))
    adapter.core.RESULTS_Q2=root/'q2';adapter.shift.RESULTS_Q2=root/'q2';adapter.exporter.RESULTS_Q2=root/'q2'
    proposals=read(prior/'proposals.json');groups={tuple(sorted(g['task_ids'])) for p in proposals for g in p['groups']}
    ids=list(e.atoms.index)
    for kind in ['unit','atomic','duration']:
        for g in partition(e,ids,kind):groups.add(tuple(sorted(g['task_ids'])))
    groups.update((a,) for a in ids)
    # Add neighboring common-site pairs of atomic demands: a finite expansion.
    # Limit none of the 118 common sites; no external grouping imported.
    ordered=sorted(ids,key=lambda a:(float(e.atoms.loc[a].service_start_s),a))
    for i,a in enumerate(ordered):
        for b in ordered[i+1:i+3]:
            if e.common([a,b]):groups.add(tuple(sorted([a,b])))
    flights=adapter.read(e.base/'q2_sorties.csv');zero={s:0. for s in flights.sortie_id}
    references=[zero,{r.sortie_id:-float(r.preparation_start_s) for r in flights.itertuples()}]
    modes={}
    for tasks in sorted(groups):
        minimum=max(float(e.atoms.loc[a].service_duration_s) for a in tasks)
        sites=[s for s in sorted(e.common(tasks)) if e.energy(e.sites[s],0)['total_energy_kwh']+(e.pr['hover_power_kw']+e.pr['comm_power_kw'])*minimum/3600<=(1-e.pr['rho'])*e.pr['energy_kwh']+1e-10]
        if not sites:continue
        for shifts in references:
            mode=endpoint_mode(e,tasks,dict(shifts=shifts),'COLD_AUTONOMOUS_PROPOSAL_NOT_A_VERIFIED_WITNESS')
            key=signature({k:mode[k] for k in ('task_ids','events')})
            modes[key]=dict(mode,id=key,sites=sites,minimum_duration_s=minimum)
    # Atomic-pair expansion can be large; all resulting modes are retained.
    modes=[modes[k] for k in sorted(modes)];write(root/'group_mode_catalogue.json',modes)
    model=AuditModel(e,modes,dict(groups=proposals[0]['groups']));a,lo,hi=model.arrays();c=model.objective('relay_sorties')
    write(root/'domain.json',dict(scope='EXACT_PARTIAL_FINITE_GROUP_AND_ENDPOINT_ORDER_DOMAIN',groups=len(groups),modes=len(modes),variables=len(model.names),constraints=a.shape[0],
        group_sources='Three batch partitions; three global greedy partitions; all atoms; common-site pairs within two neighbors in nominal task-start order',
        endpoint_orders='Q2 schedule order and all preparations-at-zero order; other permutations not enumerated',
        resource_assignments_and_orders_free=True,all_common_frozen_sites=True,exact_union_energy=True,exact_charge_graph=True,
        Gamma_C_db=0,seed=26092511,threads=1,late_hard_layer=1e-4,global_Q3_optimality_claim=False))
    np.savez_compressed(root/'model.npz',data=a.data,indices=a.indices,indptr=a.indptr,shape=a.shape,lower=lo,upper=hi,lb=model.lb,ub=model.ub,integrality=model.integer,objective=c)
    au,bu,ae,be,um,em=lp_form(a,lo,hi);start=time.process_time()
    lp=linprog(c,A_ub=au,b_ub=bu,A_eq=ae,b_eq=be,bounds=list(zip(model.lb,model.ub)),method='highs',options=dict(threads=1,time_limit=60));lp_cpu=time.process_time()-start;bound=None
    if lp.success:
        cert=rational_lagrangian_bound(c,a,lo,hi,model.lb,model.ub,um,em,lp.ineqlin.marginals,lp.eqlin.marginals);cert['matrix_sha256']=digest(root/'model.npz');write(root/'certificate.json',cert)
        bound=math.ceil(Fraction(int(cert['numerator']),int(cert['denominator'])))
    print('EXACT_MODEL',pid,len(modes),len(model.names),a.shape[0],'LB',bound,flush=True)
    start=time.process_time();sol=milp(c,integrality=model.integer,bounds=Bounds(model.lb,model.ub),constraints=LinearConstraint(a,lo,hi),
        options=dict(threads=1,random_seed=26092511,time_limit=args.limit,mip_rel_gap=1e-6,presolve=False));mip_cpu=time.process_time()-start
    def finite(x):return None if x is None or not math.isfinite(float(x)) else float(x)
    result=dict(pid=pid,status=int(sol.status),message=str(sol.message),raw_objective=finite(sol.fun),raw_dual_bound=finite(getattr(sol,'mip_dual_bound',None)),raw_mip_gap=finite(getattr(sol,'mip_gap',None)),
        mip_cpu_s=mip_cpu,lp_cpu_s=lp_cpu,lp_status=int(lp.status),lp_iterations=int(lp.nit),nodes=None if getattr(sol,'mip_node_count',None) is None else int(sol.mip_node_count),
        certified_relay_count_lower_bound=bound,bound_scope='Declared exact partial group/order/site domain only',witnesses=[],infeasibility_proven=False)
    write(root/'result.json',result)
    if sol.x is not None:
        np.save(root/'solver_incumbent.npy',sol.x)
        try:
            bounds=[(round(sol.x[i]),round(sol.x[i])) if b else (model.lb[i],model.ub[i]) for i,b in enumerate(model.integer)]
            late=csr_matrix(([float(w) for w in model.core.weights],([0]*len(model.late),model.late)),shape=(1,len(sol.x)))
            start=time.process_time();polish=linprog(model.objective('joint_makespan_s'),A_ub=vstack([au,late]),b_ub=np.r_[bu,9.99e-5],A_eq=ae,b_eq=be,bounds=bounds,method='highs',options=dict(threads=1,time_limit=30,primal_feasibility_tolerance=1e-9));polish_cpu=time.process_time()-start
            write(root/'primal_polish.json',dict(status=int(polish.status),cpu_s=polish_cpu,scope='Fixed integer primal makespan tie-break only, not a lower bound'))
            x=polish.x if polish.success else sol.x;answer=model.materialize(x,'relay_sorties')
            assert answer['metrics']['J_late']<=1e-4 and max(model.violation(x).values())<=1e-5
            ident=pid+'_Q3_EXACT_001';adapter.export_local(e,copy.deepcopy(answer),ident);package=e.dest/'solutions'/ident
            mm=read(package/f'joint_metrics_{pid}.json');mm.update(source_provenance='P1_3B_AUTONOMOUS_POOL_EXACT_SCREEN');write(package/f'joint_metrics_{pid}.json',mm)
            validation=audit(root,pid,package);assert validation['J_late']<=1e-4
            result['witnesses'].append(dict(id=ident,metrics=answer['metrics'],package=str(package.relative_to(ROOT)),validation=validation,validation_sha256=digest(package/'validation_0.5.json')))
        except Exception as exc:result['candidate_rejection']=repr(exc)
    result['total_cpu_s']=time.process_time()-tick;write(root/'result.json',result);print('EXACT_DONE',pid,'witnesses',len(result['witnesses']),result.get('candidate_rejection'),flush=True)

if __name__=='__main__':main()
