"""Isolated P1 fork of finite relay-order MILP with preference objective."""
from src.q3.e8_candidates import *
from src.q3.e7_core import Timing,sequences_for,objective_key,improves
from src.q3.e7_search import search
from src.q3.e7_pareto import nondominated,unique_results
from scipy.optimize import milp,Bounds,LinearConstraint
from scipy.sparse import coo_matrix


def relay_order_milp(e,groups,limit=60,joint_resources=False,preference=None):
    model=Timing(e,'P01',groups);n=model.dim;k=len(groups)
    rows=list(model.rows);upper=list(model.upper);lower=[-np.inf]*len(rows)
    costs=list(model.late_c);bounds=list(model.bounds);integrality=[0]*n
    def var():
        j=len(costs);costs.append(0);bounds.append((0,1));integrality.append(1);return j
    def add(row,lo=-np.inf,hi=np.inf):rows.append(row);lower.append(lo);upper.append(hi)
    assign=[[var(),var()] for _ in groups]
    for a,b in assign:add({a:1,b:1},1,1)
    bounds[assign[0][0]]=(1,1);M=100000.
    for i in range(k):
        for j in range(i+1,k):
            for r in range(2):
                z=var();si=model.n+2*i;ei=si+1;sj=model.n+2*j;ej=sj+1
                add({ei:1,sj:-1,z:M,assign[i][r]:M,assign[j][r]:M},hi=3*M-model.tails[i]-model.leads[j])
                add({ej:1,si:-1,z:-M,assign[i][r]:M,assign[j][r]:M},hi=2*M-model.tails[j]-model.leads[i])
    if joint_resources:
        for kind,typ,specs,allowed in model.resource_specs:
            aa=[[var() for _ in allowed] for _ in specs]
            for row in aa:add({v:1 for v in row},1,1)
            bounds[aa[0][0]]=(1,1)
            for ii,(i,istart,iend) in enumerate(specs):
                for jj in range(ii+1,len(specs)):
                    j,jstart,jend=specs[jj];z=var()
                    for r in range(len(allowed)):
                        add({i:1,j:-1,z:M,aa[ii][r]:M,aa[jj][r]:M},hi=3*M-iend+jstart-1e-5)
                        add({j:1,i:-1,z:-M,aa[ii][r]:M,aa[jj][r]:M},hi=2*M-jend+istart-1e-5)
    rr=[];cc=[];vv=[]
    for i,row in enumerate(rows):
        for j,v in row.items():rr.append(i);cc.append(j);vv.append(v)
    a=coo_matrix((vv,(rr,cc)),shape=(len(rows),len(costs))).tocsc()
    lo=np.array([b[0] if b[0] is not None else -np.inf for b in bounds]);hi=np.array([b[1] if b[1] is not None else np.inf for b in bounds])
    tick=time.monotonic();sol=milp(np.array(costs),integrality=np.array(integrality),bounds=Bounds(lo,hi),
        constraints=LinearConstraint(a,np.array(lower),np.array(upper)),options=dict(time_limit=limit,mip_rel_gap=.01))
    info=dict(status=int(sol.status),message=str(sol.message),runtime_s=time.monotonic()-tick,groups=k,
              objective=None if sol.fun is None else float(sol.fun),dual_bound=None if getattr(sol,'mip_dual_bound',None) is None else float(sol.mip_dual_bound),
              scope='JOINT_TYPED_RESOURCES_MILP' if joint_resources else 'RELAY_ORDER_SEED_ONLY_TRANSPORT_RESOURCES_REQUIRE_REPAIR',limit_s=limit)
    if sol.x is None:return None,info
    if preference is not None:
        primary=np.array(costs);cost=np.zeros(len(costs));w=preference.weight;s=preference.scales
        cost[:model.dim]=model.norm_c*w[0]/s[0];cost[model.makespan]+=w[1]/s[1]
        for j in range(model.k):
            power=e.pr['hover_power_kw']+e.pr['comm_power_kw']
            cost[model.n+2*j]-=power/3600*w[2]/s[2];cost[model.n+2*j+1]+=power/3600*w[2]/s[2]
        from scipy.sparse import vstack,csr_matrix
        second=milp(cost,integrality=np.array(integrality),bounds=Bounds(lo,hi),
          constraints=LinearConstraint(vstack([a,csr_matrix(primary)]),np.r_[lower,-np.inf],np.r_[upper,primary@sol.x+1e-7]),
          options=dict(time_limit=limit,mip_rel_gap=.01))
        if second.x is not None:sol=second
        preference.event('q3_milp_objective',fixed_transport_sorties=model.n,fixed_relay_sorties=model.k,energy_objective='CONSERVATIVE_ACTIVE_POWER_SPAN_SURROGATE_ACTUAL_ENERGY_RECHECKED')
    seq=[sorted([i for i in range(k) if sol.x[assign[i][r]]>.5],key=lambda i:sol.x[model.n+2*i]) for r in range(2)]
    answer=model.solve(seq,node_limit=120)
    if answer is None and joint_resources:answer=model.materialize(sol.x[:n],seq,())
    info['transport_resource_repair_passed']=answer is not None
    return answer,info

