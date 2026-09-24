"""E8 robustness scenarios reuse the E7 timing and epsilon neighborhood kernels."""
from src.q3.e8_candidates import *
from src.q3.e7_core import Timing,sequences_for,objective_key,improves
from src.q3.e7_search import search
from src.q3.e7_pareto import nondominated,unique_results
from scipy.optimize import milp,Bounds,LinearConstraint
from scipy.sparse import coo_matrix


def load_engine(gamma):
    e=RobustEngine(gamma);dest=gamma_dir(gamma)
    for r in read(dest/'candidate_sites.csv').to_dict('records'):
        s=e.add_site(r['x_m'],r['y_m'],r['agl_m']);assert s['site_id']==r['site_id']
    for r in read(dest/'candidate_pairs.csv').to_dict('records'):e.edges['P01'][r['atomic_task_id']][r['site_id']]=r
    return e


def mapped_groups(e,seed):
    old=read(E6/'guarded_atomic_tasks.csv').set_index('atomic_task_id');groups=[];mapping={};used=set()
    def partition(ids):
        units=[]
        for sid,frame in e.atoms.loc[ids].groupby('transport_sortie_id'):
            aa=list(frame.atomic_task_id)
            if e.common(aa):units.append(aa)
            else:units.extend([[a] for a in aa])
        result=[]
        while units:
            choices=[]
            sites=set.union(*(e.common(u) for u in units))
            for sid in sorted(sites):
                covered=[i for i,u in enumerate(units) if sid in e.common(u)]
                en=e.energy(e.sites[sid],0)
                choices.append((-len(covered),en['outbound_time_s']+en['return_time_s'],sid,covered))
            _,_,sid,covered=min(choices)
            aa=sorted(a for i in covered for a in units[i]);result.append(dict(site_id=sid,task_ids=aa))
            units=[u for i,u in enumerate(units) if i not in covered]
        return result
    for j,g in enumerate(seed['groups']):
        transports={old.loc[a].transport_sortie_id for a in g['task_ids']}
        ids=[a for a in e.atoms[e.atoms.transport_sortie_id.isin(transports)].atomic_task_id if a not in used]
        used.update(ids);new=partition(ids) if ids else []
        mapping[j]=list(range(len(groups),len(groups)+len(new)));groups+=new
    sequences=[[x for j in seq for x in mapping[j]] for seq in seed['sequences']]
    left=[a for a in e.atoms.index if a not in used]
    if left:
        for g in partition(left):
            # Place new robust-only work by its original earliest service time.
            t=min(e.atoms.loc[a].service_start_s for a in g['task_ids']);j=len(groups);groups.append(g)
            choices=[]
            for r,seq in enumerate(sequences):
                pos=sum(min(e.atoms.loc[a].service_start_s for a in groups[k]['task_ids'])<t for k in seq)
                choices.append((len(seq),r,pos))
            _,r,pos=min(choices);sequences[r].insert(pos,j)
    assert sorted(a for g in groups for a in g['task_ids'])==sorted(e.atoms.index)
    return groups,sequences


def relay_order_milp(e,groups,limit=60,joint_resources=False):
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
    seq=[sorted([i for i in range(k) if sol.x[assign[i][r]]>.5],key=lambda i:sol.x[model.n+2*i]) for r in range(2)]
    answer=model.solve(seq,node_limit=120)
    if answer is None and joint_resources:answer=model.materialize(sol.x[:n],seq,())
    info['transport_resource_repair_passed']=answer is not None
    return answer,info


def find_seed(gamma):
    e=load_engine(gamma);attempts=[];best=None
    for name in ['Q3E7_001','Q3E7_008']:
        seed=json.loads((E7/'solutions'/name/'witness.json').read_text());groups,seq=mapped_groups(e,seed)
        tick=time.monotonic();answer=Timing(e,'P01',groups).solve(seq,node_limit=120)
        info=dict(source=name,groups=groups,sequences=seq,lp_seed_feasible=answer is not None,lp_runtime_s=time.monotonic()-tick)
        if answer is None:
            answer,m=relay_order_milp(e,groups,limit=60);info['milp']=m
        attempts.append(info);write_json(gamma_dir(gamma)/'seed_search.json',attempts)
        if answer:
            answer['Gamma_C_db']=gamma
            if best is None or improves(answer,best,'timeliness'):best=answer
        print('SEED',gamma,name,len(groups),answer['metrics'] if answer else None,flush=True)
    if best:write_json(gamma_dir(gamma)/'seed.json',best)
    else:write_json(gamma_dir(gamma)/'scenario_status.json',dict(status='BLOCKED_UNDER_CURRENT_BOUNDED_SEARCH',physical_infeasibility_proven=False))
    return e,best


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--gamma',type=float,required=True);a=p.parse_args();find_seed(a.gamma)
