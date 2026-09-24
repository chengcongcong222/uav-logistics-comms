"""Joint site, task assignment and timing MILP for critical early relays.

This is a bounded seed search, not a physical infeasibility certificate.
"""
from src.q3.e8_seed_variants import *

def run(gamma,slots_per_aircraft=2):
    e=load_engine(gamma);dest=gamma_dir(gamma)
    atoms=[a for a in e.atoms.index if int(e.atoms.loc[a].transport_sortie_id[1:])<=8]
    # Equivalent coverage signatures retain the shortest relay round trip.
    signatures={}
    for site in sorted(set.union(*(e.common([a]) for a in atoms))):
        sig=tuple(a for a in atoms if site in e.common([a]));en=e.energy(e.sites[site],0)
        cost=en['outbound_time_s']+en['return_time_s']
        if sig not in signatures or cost<signatures[sig][0]:signatures[sig]=(cost,site)
    sites=sorted(v[1] for v in signatures.values());model=Timing(e,'P01',[])
    rows=list(model.rows);hi=list(model.upper);lo=[-np.inf]*len(rows);costs=list(model.late_c);bounds=list(model.bounds);integ=[0]*len(costs)
    def var(lower=0,upper=1,integer=1):
        j=len(costs);costs.append(0);bounds.append((lower,upper));integ.append(integer);return j
    def add(row,lower=-np.inf,upper=np.inf):rows.append(row);lo.append(lower);hi.append(upper)
    k=2*slots_per_aircraft;ss=[var(0,40000,0) for _ in range(k)];ee=[var(0,40000,0) for _ in range(k)]
    yy=[[var() for s in sites] for j in range(k)];xx={a:[var() for j in range(k)] for a in atoms};M=100000.
    leads=[];tails=[];spans=[]
    for s in sites:
        en=e.energy(e.sites[s],0);leads.append(210+en['outbound_time_s']);tails.append(300+en['return_time_s'])
        spans.append(((1-e.pr['rho'])*e.pr['energy_kwh']-en['total_energy_kwh'])*3600/1.1)
    for j in range(k):
        add({v:1 for v in yy[j]},1,1)
        add({ss[j]:-1,**{v:lead for v,lead in zip(yy[j],leads)}},upper=0)
        add({ee[j]:1,ss[j]:-1,**{v:-span for v,span in zip(yy[j],spans)}},upper=0)
        add({ss[j]:1,ee[j]:-1},upper=0)
        add({xx[a][j]:1 for a in atoms},lower=1)
        if j%slots_per_aircraft:
            add({ee[j-1]:1,ss[j]:-1,**{v:t for v,t in zip(yy[j-1],tails)},**{v:t for v,t in zip(yy[j],leads)}},upper=0)
    for a in atoms:
        t=e.atoms.loc[a];i=model.idx[t.transport_sortie_id];add({v:1 for v in xx[a]},1,1)
        for j in range(k):
            add({xx[a][j]:1,**{yy[j][q]:-1 for q,s in enumerate(sites) if s in e.common([a])}},upper=0)
            add({ss[j]:1,i:-1,xx[a][j]:M},upper=float(t.service_start_s)+M)
            add({ee[j]:-1,i:1,xx[a][j]:M},upper=-float(t.service_end_s)+M)
    # Only early transportation resource constraints are needed in this seed
    # relaxation. Full 28-flight resources are imposed by the second MILP.
    for kind,typ,all_specs,allowed in model.resource_specs:
        specs=[r for r in all_specs if int(model.ids[r[0]][1:])<=8]
        if len(specs)<=len(allowed):continue
        aa=[[var() for r in allowed] for s in specs]
        for a in aa:add({v:1 for v in a},1,1)
        bounds[aa[0][0]]=(1,1)
        for ii,(i,istart,iend) in enumerate(specs):
            for jj in range(ii+1,len(specs)):
                z=var();j,jstart,jend=specs[jj]
                for r in range(len(allowed)):
                    add({i:1,j:-1,z:M,aa[ii][r]:M,aa[jj][r]:M},upper=3*M-iend+jstart-1e-5)
                    add({j:1,i:-1,z:-M,aa[ii][r]:M,aa[jj][r]:M},upper=2*M-jend+istart-1e-5)
    rr=[];cc=[];vv=[]
    for i,row in enumerate(rows):
        for j,v in row.items():rr.append(i);cc.append(j);vv.append(v)
    mat=coo_matrix((vv,(rr,cc)),shape=(len(rows),len(costs))).tocsc()
    lb=[b[0] if b[0] is not None else -np.inf for b in bounds];ub=[b[1] if b[1] is not None else np.inf for b in bounds]
    tick=time.monotonic();sol=milp(np.array(costs),integrality=np.array(integ),bounds=Bounds(lb,ub),constraints=LinearConstraint(mat,lo,hi),options=dict(time_limit=120,mip_rel_gap=.01))
    info=dict(status=int(sol.status),message=str(sol.message),runtime_s=time.monotonic()-tick,candidate_signatures=len(sites),slots_per_aircraft=slots_per_aircraft,objective=None if sol.fun is None else float(sol.fun),global_physical_infeasibility_proven=False)
    print('ASSIGNMENT',info,flush=True)
    if sol.x is not None:
        groups=[dict(site_id=sites[int(np.argmax([sol.x[v] for v in yy[j]]))],task_ids=[a for a in atoms if sol.x[xx[a][j]]>.5]) for j in range(k)]
        for start in [9,17,25]:
            ids=[a for a in e.atoms.index if start<=int(e.atoms.loc[a].transport_sortie_id[1:])<start+8]
            if ids:groups+=partition(e,ids,'unit')
        ans,joint=relay_order_milp(e,groups,limit=90,joint_resources=True);info['joint']=joint;info['groups_definition']=groups
        if ans:ans['Gamma_C_db']=gamma;write_json(dest/'seed.json',ans)
    write_json(dest/f'assignment_seed_{slots_per_aircraft}.json',info)

if __name__=='__main__':
    import sys
    run(float(sys.argv[1]),int(sys.argv[2]) if len(sys.argv)>2 else 2)
