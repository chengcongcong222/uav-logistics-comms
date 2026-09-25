"""Bounded mathematical audit of one fixed autonomous transport structure."""
import argparse, copy, json, math, shutil, time, warnings
from pathlib import Path
import numpy as np
from scipy.optimize import milp,linprog,Bounds,LinearConstraint
from scipy.sparse import csr_matrix,vstack
from src.bench_p1.common import ROOT,write,digest,signature
from src.bench_p1 import q3_adapter as adapter
from src.bench_p1_2.driver import audit,remap_sites
from src.bench_p1_3a.model import AXES,AuditModel,catalogue,lp_form,rational_lagrangian_bound

OUT=ROOT/'results/p1_3a'
SEED=26092511

def finite(v):return float(v) if v is not None and math.isfinite(float(v)) else None
def metric_key(row,axis):
    m=row['metrics'];order=[axis]+[k for k in ('J_norm','joint_makespan_s','total_energy_kwh','transport_sorties','relay_sorties') if k!=axis]
    return tuple(m[k] for k in order)+(row['id'],)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('pid',choices=['A11','AN01','A03'])
    parser.add_argument('--limit',type=float,default=90);parser.add_argument('--revision',default='v3')
    parser.add_argument('--no-presolve',action='store_true');args=parser.parse_args()
    warnings.filterwarnings('ignore',message='Unrecognized options detected')
    root=OUT/'runs'/args.revision/args.pid
    if root.exists():raise RuntimeError('Refuse to overwrite audit run')
    root.mkdir(parents=True);tick=time.process_time()
    config=dict(mode='STRUCTURE_FIXED_EXACT_AUDIT',pid=args.pid,solver_seed=SEED,formal_seed=False,
                mip_limit_per_anchor_s=args.limit,lp_limit_per_anchor_s=60,threads=1,
                mip_relative_gap_tolerance=1e-6,zero_lateness_hard_layer=1e-4,
                objective_order=list(AXES),tie_break='INCUMBENT_SELECTION_ONLY: anchor, J_norm, makespan, energy, transport, relay, ID; no secondary optimality claim',
                no_external_targets=True,mip_presolve=not args.no_presolve,source_hashes={str(p.relative_to(ROOT)):digest(p) for p in (ROOT/'src/bench_p1_3a').glob('*.py')})
    write(root/'config.json',config)
    inputs=json.loads((OUT/'inputs.json').read_text());records=[r for r in inputs['sources'] if r['pid']==args.pid]
    base=root/'q2/pareto_schedules'/args.pid
    shutil.copytree(OUT/'admission/q2/pareto_schedules'/args.pid,base)
    print('BUILD_PRIVATE_COMMUNICATION',args.pid,flush=True)
    e=adapter.Engine(root,args.pid,lambda stage:print(args.pid,stage,flush=True));e.pool()
    assert len(e.sites)==118
    adapter.core.RESULTS_Q2=root/'q2';adapter.shift.RESULTS_Q2=root/'q2';adapter.exporter.RESULTS_Q2=root/'q2'
    witnesses=[];rows=[]
    for rec in records:
        package=ROOT/rec['package'];assert digest(package/'witness.json')==rec['witness_sha256']
        w=json.loads((package/'witness.json').read_text())
        w,mapping=remap_sites(e,w,adapter.read(package/f'candidate_sites_{args.pid}.csv').to_dict('records'))
        assert sorted(t for g in w['groups'] for t in g['task_ids'])==sorted(e.atoms.index)
        witnesses.append(w);rows.append(dict(id=rec['id'],metrics=w['metrics'],witness=w,package=rec['package'],origin='HASH_BOUND_INTERNAL_WARM'))
    modes=catalogue(e,witnesses);write(root/'group_mode_catalogue.json',modes)
    model=AuditModel(e,modes,witnesses[0]);a,lo,hi=model.arrays()
    write(root/'model_summary.json',dict(variables=len(model.names),binary_variables=sum(model.integer),constraints=a.shape[0],nonzero_coefficients=a.nnz,
         group_modes=len(modes),site_options=sum(len(m['sites']) for m in modes),transport_sorties=model.n,
         no_warm_resource_orders_fixed=True,energy='EXACT_FIXED_ENDPOINT_ORDER_UNION',charge='EXACT_TWO_PIECE_GRAPH'))
    warm=[];embedded=[]
    for row in rows:
        if row['metrics']['J_late']>1e-4:continue
        x=model.embed(row['witness']);violation=model.violation(x)
        mismatch={axis:float(model.objective(axis)@x)-row['metrics'][axis] for axis in AXES}
        check=dict(id=row['id'],violation=violation,objective_residuals=mismatch)
        embedded.append(check)
        if max(violation.values())>1e-5 or max(abs(v) for v in mismatch.values())>1e-5:
            write(root/'warm_embedding.json',embedded);raise AssertionError(('Warm witness not in declared exact domain',check))
        warm.append(row)
    write(root/'warm_embedding.json',embedded)
    print('MODEL_PASS',args.pid,len(modes),len(model.names),a.shape[0],'zero_warm',len(warm),flush=True)
    results=[];audit_records=[];serial=0
    for axis in AXES:
        dest=root/'anchors'/axis;dest.mkdir(parents=True)
        c=model.objective(axis);aa=a;ll=lo.copy();hh=hi.copy()
        incumbent=min(warm,key=lambda r:metric_key(r,axis)) if warm else None
        cutoff=None
        # v2: keep the full declared domain; verified warm values are external
        # primal bounds, never near-tight numerical objective constraints.
        np.savez_compressed(dest/'model.npz',data=aa.data,indices=aa.indices,indptr=aa.indptr,shape=aa.shape,
                lower=ll,upper=hh,lb=np.array(model.lb),ub=np.array(model.ub),integrality=np.array(model.integer),objective=c)
        write(dest/'model_identity.json',dict(matrix_sha256=digest(dest/'model.npz'),catalogue_sha256=digest(root/'group_mode_catalogue.json'),
                 objective=axis,cutoff=cutoff,cutoff_source=incumbent['id'] if incumbent else None,
                 variables=model.names,coefficient_domain='STORED_BINARY64_COEFFICIENTS'))
        au,bu,ae,be,u_map,e_map=lp_form(aa,ll,hh)
        start=time.process_time()
        lp=linprog(c,A_ub=au,b_ub=bu,A_eq=ae,b_eq=be,bounds=list(zip(model.lb,model.ub)),method='highs',
             options=dict(threads=1,time_limit=60,primal_feasibility_tolerance=1e-8,dual_feasibility_tolerance=1e-8))
        lp_cpu=time.process_time()-start;certificate=None
        if lp.success:
            cert_start=time.process_time()
            certificate=rational_lagrangian_bound(c,aa,ll,hh,model.lb,model.ub,u_map,e_map,
                          lp.ineqlin.marginals if au is not None else [],lp.eqlin.marginals if ae is not None else [])
            certificate.update(matrix_sha256=digest(dest/'model.npz'),lp_value=float(lp.fun),certificate_cpu_s=time.process_time()-cert_start)
            write(dest/'lp_lower_bound_certificate.json',certificate)
        print('LP_BOUND',args.pid,axis,certificate['lower_bound'] if certificate else None,flush=True)
        start=time.process_time()
        sol=milp(c,integrality=np.array(model.integer),bounds=Bounds(model.lb,model.ub),constraints=LinearConstraint(aa,ll,hh),
            options=dict(threads=1,time_limit=args.limit,mip_rel_gap=1e-6,random_seed=SEED,mip_feasibility_tolerance=1e-8,presolve=not args.no_presolve))
        mip_cpu=time.process_time()-start;candidate=None;validation=None;candidate_error=None
        contradiction=bool(sol.status==2 and warm)
        if contradiction:
            write(dest/'solver_status_contradiction.json',dict(status=int(sol.status),message=str(sol.message),warm_ids=[r['id'] for r in warm],claim='DO_NOT_ACCEPT_SOLVER_INFEASIBILITY_OR_BNB_BOUND'))
        if sol.x is not None:
            np.save(dest/'solver_incumbent.npy',sol.x)
            try:
                x=sol.x.copy();polish_cpu=0.
                answer=model.materialize(x,axis)
                if answer['metrics']['J_late']>1e-4:
                    # Primal-only repair with fixed integer choices. This
                    # strictly smaller layer never supplies a lower bound.
                    polish_start=time.process_time()
                    bounds=[(round(x[i]),round(x[i])) if b else (model.lb[i],model.ub[i]) for i,b in enumerate(model.integer)]
                    late=csr_matrix(([float(w) for w in model.core.weights],([0]*len(model.late),model.late)),shape=(1,len(x)))
                    fixed=linprog(c,A_ub=vstack([au,late]).tocsr(),b_ub=np.r_[bu,1e-4-1e-7],A_eq=ae,b_eq=be,bounds=bounds,method='highs',options=dict(threads=1,time_limit=30,primal_feasibility_tolerance=1e-9,dual_feasibility_tolerance=1e-9))
                    polish_cpu=time.process_time()-polish_start
                    write(dest/'primal_polish.json',dict(status=int(fixed.status),message=str(fixed.message),cpu_s=polish_cpu,primal_only=True,never_used_as_lower_bound=True))
                    if fixed.success:
                        x=fixed.x;np.save(dest/'polished_incumbent.npy',x);answer=model.materialize(x,axis)
                if answer['metrics']['J_late']>1e-4:raise ValueError('Numerical candidate outside zero-lateness hard layer')
                residual={k:float(model.objective(k)@x)-answer['metrics'][k] for k in AXES}
                checks=[abs(v) for k,v in residual.items() if k!='joint_makespan_s']
                checks.append(abs(residual['joint_makespan_s']) if axis=='joint_makespan_s' else max(0.,-residual['joint_makespan_s']))
                if max(checks)>2e-5:raise ValueError(('Physical/linear objective mismatch',residual))
                if max(model.violation(x).values())>1e-5:raise ValueError(('Compiled MILP constraint violation',model.violation(x)))
                serial+=1;ident=f'{args.pid}_P13A_{serial:03d}'
                adapter.export_local(e,copy.deepcopy(answer),ident);package=e.dest/'solutions'/ident
                metric_path=package/f'joint_metrics_{args.pid}.json'
                mm=json.loads(metric_path.read_text());mm.update(mode='STRUCTURE_FIXED_EXACT_AUDIT',source_provenance='AUTONOMOUS_INTERNAL_FIXED_STRUCTURE',formal_cold_start_eligible=False)
                write(metric_path,mm)
                validation=audit(root,args.pid,package)
                candidate=dict(id=ident,metrics=answer['metrics'],witness=answer,package=str(package.relative_to(ROOT)),origin='MILP_INDEPENDENTLY_VALIDATED')
                warm.append(candidate)
                audit_records.append(dict(id=ident,status='INDEPENDENTLY_VALIDATED',anchor=axis,pid=args.pid,package=str(package.relative_to(ROOT)),result=validation,linear_objective_residuals=residual))
            except Exception as exc:
                candidate_error=repr(exc)
                write(dest/'candidate_rejection.json',dict(error=candidate_error,solver_status=int(sol.status)))
                audit_records.append(dict(anchor=axis,pid=args.pid,status='CANDIDATE_REJECTED_NOT_AN_INCUMBENT',error=candidate_error))
        incumbent=min(warm,key=lambda r:metric_key(r,axis)) if warm else None
        ub=float(incumbent['metrics'][axis]) if incumbent else None
        solver_lb=finite(getattr(sol,'mip_dual_bound',None));cert_lb=certificate['lower_bound'] if certificate else None
        bound_conflict=bool(ub is not None and solver_lb is not None and solver_lb>ub+max(1e-5,abs(ub)*1e-7))
        if bound_conflict:
            write(dest/'solver_bound_contradiction.json',dict(solver_dual_bound=solver_lb,verified_incumbent=ub,status=int(sol.status),message=str(sol.message),claim='BOUND_NOT_VALID: RAW_BNB_BOUND_REJECTED'))
        valid_bounds=[x for x in [None if contradiction or bound_conflict else solver_lb,cert_lb] if x is not None]
        bound=max(valid_bounds) if valid_bounds else None
        if ub is not None and bound is not None and bound>ub+max(1e-5,abs(ub)*1e-7):
            raise AssertionError(('Lower bound exceeds verified incumbent',args.pid,axis,bound,ub))
        gap=max(0.,(ub-bound)/max(abs(ub),1e-12)) if ub is not None and bound is not None else None
        cert_gap=max(0.,(ub-cert_lb)/max(abs(ub),1e-12)) if ub is not None and cert_lb is not None else None
        optimal=bool(sol.status==0 and incumbent is not None and gap is not None and gap<=1.1e-6 and candidate_error is None)
        row=dict(pid=args.pid,anchor=axis,mode='STRUCTURE_FIXED_EXACT_AUDIT',incumbent=None if incumbent is None else {k:v for k,v in incumbent.items() if k!='witness'},
            best_feasible_value=ub,solver_lower_bound=solver_lb,certified_lp_lower_bound=cert_lb,
            best_reported_lower_bound=bound,verified_incumbent_relative_gap=gap,certified_lp_relative_gap=cert_gap,
            solver_mip_gap=finite(getattr(sol,'mip_gap',None)),solver_incumbent_value=finite(sol.fun),
            termination_status=int(sol.status),termination_message=str(sol.message),
            mip_cpu_s=mip_cpu,lp_cpu_s=lp_cpu,mip_nodes=None if getattr(sol,'mip_node_count',None) is None else int(sol.mip_node_count),
            lp_iterations=int(lp.nit),lp_status=int(lp.status),lp_message=str(lp.message),
            finite_domain_optimal_within_solver_tolerance=optimal,Q3_global_optimal=False,
            bound_status='VALID_FOR_DECLARED_FINITE_MILP' if bound is not None else 'BOUND_NOT_VALID',
            lp_certificate_status='EXACT_RATIONAL_LAGRANGIAN' if certificate else 'NO_CERTIFICATE',
            candidate_error=candidate_error,matrix=str((dest/'model.npz').relative_to(ROOT)),
            solver_infeasibility_conflicts_with_verified_warm=contradiction,solver_bound_conflicts_with_verified_warm=bound_conflict,
            warm_start_mechanism='VERIFIED_EXTERNAL_INCUMBENT_ONLY_NO_CUTOFF; scipy.milp has no supplied primal MIP-start in this driver',
            mip_iterations=None,mip_iterations_note='Not exposed by scipy.milp result')
        results.append(row);write(root/'extreme_results.json',results);write(root/'independent_audit.json',audit_records)
        print('ANCHOR_DONE',args.pid,axis,'UB',ub,'LB',bound,'GAP',gap,'status',sol.status,flush=True)
    results.append(dict(pid=args.pid,anchor='transport_sorties',fixed_structure_constant=model.n,
          best_feasible_value=model.n if warm else None,lower_bound=model.n,
          finite_domain_optimal_within_solver_tolerance=bool(warm),zero_late_feasibility_witness=bool(warm),
          note='Constant conditional on feasibility; no transportation structure enumeration in this phase'))
    write(root/'extreme_results.json',results)
    write(root/'timing.json',dict(total_process_cpu_s=time.process_time()-tick,formal_equal_cpu_comparison=False))

if __name__=='__main__':main()
