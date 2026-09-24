"""Single feasibility-only rescue, with no two/three-sortie cap per relay."""
from src.q3.e81_prepare import *

def run():
    assert not (E81/'feasibility_search.json').exists(),'The authorized one rescue search is already recorded'
    e=engine();config=json.loads((E81/'config.json').read_text());critical=set(config['critical_transport_ids'])
    atoms=sorted(a for a in e.atoms.index if e.atoms.loc[a].transport_sortie_id in critical)
    outside=json.loads((E81/'outside_window_groups.json').read_text());na=len(atoms);k=na+len(outside)
    model=Timing(e,'P01',[]);rows=list(model.rows);upper=list(model.upper);lower=[-np.inf]*len(rows)
    bounds=list(model.bounds);integ=[0]*model.dim;costs=[0.]*model.dim;M=100000.
    def var(lo=0,hi=1,integer=1):
        j=len(costs);costs.append(0.);bounds.append((lo,hi));integ.append(integer);return j
    def add(row,lo=-np.inf,hi=np.inf):rows.append(row);lower.append(lo);upper.append(hi)
    starts=[var(0,40000,0) for _ in range(k)];ends=[var(0,40000,0) for _ in range(k)]
    active=[var(1 if j>=na else 0,1) for j in range(k)];relay=[[var(),var()] for _ in range(k)]
    sites=[sorted(e.edges['P01'][a]) for a in atoms]+[[g['site_id']] for g in outside]
    yy=[[var() for _ in ss] for ss in sites];xx={}
    # Any partition of atomic tasks can be labelled by its smallest task index.
    # Thus one optional anchor slot per task is a lossless cardinality bound,
    # unlike limiting each aircraft to two or three sorties.
    for i,a in enumerate(atoms):
        for j in range(i+1):
            if set(sites[j])&set(e.edges['P01'][a]):xx[i,j]=var()
        add({v:1 for (ii,j),v in xx.items() if ii==i},1,1)
        add({xx[i,i]:1,active[i]:-1},0,0)
    lead_terms=[];tail_terms=[]
    for j in range(k):
        add({relay[j][0]:1,relay[j][1]:1,active[j]:-1},0,0)
        add({**{v:1 for v in yy[j]},active[j]:-1},0,0)
        lead={};tail={};span={}
        for v,s in zip(yy[j],sites[j]):
            en=e.energy(e.sites[s],0);lead[v]=210+en['outbound_time_s'];tail[v]=300+en['return_time_s']
            span[v]=((1-e.pr['rho'])*e.pr['energy_kwh']-en['total_energy_kwh'])*3600/1.1
        lead_terms.append(lead);tail_terms.append(tail)
        add({starts[j]:-1,**lead},hi=0);add({starts[j]:1,ends[j]:-1},hi=0)
        add({starts[j]:1,active[j]:-40000},hi=0);add({ends[j]:1,active[j]:-40000},hi=0)
        add({ends[j]:1,starts[j]:-1,**{v:-x for v,x in span.items()}},hi=0)
        ids=outside[j-na]['task_ids'] if j>=na else [atoms[i] for (i,jj) in xx if jj==j]
        for a in ids:
            t=e.atoms.loc[a];ti=model.idx[t.transport_sortie_id]
            if j>=na:
                add({starts[j]:1,ti:-1},hi=float(t.service_start_s));add({ends[j]:-1,ti:1},hi=-float(t.service_end_s))
            else:
                x=xx[atoms.index(a),j]
                add({x:1,**{v:-1 for v,s in zip(yy[j],sites[j]) if s in e.edges['P01'][a]}},hi=0)
                add({starts[j]:1,ti:-1,x:M},hi=float(t.service_start_s)+M)
                add({ends[j]:-1,ti:1,x:M},hi=-float(t.service_end_s)+M)
    bounds[relay[0][0]]=(1,1)  # The first anchor is necessarily used; label symmetry only.
    for i in range(k):
        for j in range(i+1,k):
            z=var()
            for r in range(2):
                add({ends[i]:1,starts[j]:-1,z:M,relay[i][r]:M,relay[j][r]:M,**tail_terms[i],**lead_terms[j]},hi=3*M)
                add({ends[j]:1,starts[i]:-1,z:-M,relay[i][r]:M,relay[j][r]:M,**tail_terms[j],**lead_terms[i]},hi=2*M)
    for kind,typ,specs,allowed in model.resource_specs:
        aa=[[var() for _ in allowed] for _ in specs]
        for v in aa:add({x:1 for x in v},1,1)
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
    mat=coo_matrix((vv,(rr,cc)),shape=(len(rows),len(costs))).tocsc()
    lo=[b[0] if b[0] is not None else -np.inf for b in bounds];hi=[b[1] if b[1] is not None else np.inf for b in bounds]
    info=dict(search_attempts=1,objective='FEASIBILITY_ONLY_ZERO_OBJECTIVE',critical_atoms=na,potential_sorties=k,
        arbitrary_per_aircraft_sortie_cap=None,outside_groups=len(outside),candidate_site_options=sum(map(len,sites)),variables=len(costs),binary_variables=sum(integ),constraints=len(rows),time_limit_s=180,
        caveats=['FINITE_CANDIDATES_AND_60S_ATOMS','OUTSIDE_GROUPS_FIXED','CONSERVATIVE_ACTIVE_SPAN_ENERGY','ENERGY_COMPONENTS_CHECKED_ON_MATERIALIZED_INCUMBENT'],physical_infeasibility_proven=False)
    write_json(E81/'feasibility_search_started.json',info);print('SEARCH_STARTED',info,flush=True)
    tick=time.monotonic();sol=milp(np.array(costs),integrality=np.array(integ),bounds=Bounds(lo,hi),constraints=LinearConstraint(mat,lower,upper),options=dict(time_limit=180,mip_rel_gap=0))
    info.update(solver_status=int(sol.status),message=str(sol.message),runtime_s=time.monotonic()-tick,incumbent_found=sol.x is not None)
    witness=None
    if sol.x is not None:
        groups=[];chosen=[]
        for j in range(k):
            if sol.x[active[j]]<.5:continue
            site=sites[j][int(np.argmax([sol.x[v] for v in yy[j]]))]
            ids=outside[j-na]['task_ids'] if j>=na else [atoms[i] for (i,jj),v in xx.items() if jj==j and sol.x[v]>.5]
            groups.append(dict(site_id=site,task_ids=ids));chosen.append(j)
        seq=[sorted([i for i,j in enumerate(chosen) if sol.x[relay[j][r]]>.5],key=lambda i:sol.x[starts[chosen[i]]]) for r in range(2)]
        check=Timing(e,'P01',groups);x=np.zeros(check.dim);x[:check.n]=sol.x[:model.n]
        # Materialization recomputes every clock from the actual demand union.
        witness=check.materialize(x,seq,())
        info['materialized_resource_check_passed']=witness is not None
        if witness:
            witness.update(Gamma_C_db=6,objective='feasibility',rescue_search=info);write_json(E81/'witness.json',witness)
            import src.q3.e8_export as exporter
            old=exporter.gamma_dir
            try:
                exporter.gamma_dir=lambda gamma:E81
                exporter.export_solution(e,witness,'Q3E81_G06_FEASIBLE',E81/'solution')
            finally:exporter.gamma_dir=old
    info['status']='WITNESS_PENDING_INDEPENDENT_VALIDATION' if witness else 'GAMMA6_NO_WITNESS_FOUND'
    info['stop_rule_reached']=True;info['next_stage']='Q4'
    write_json(E81/'feasibility_search.json',info);print('SEARCH_FINISHED',info,flush=True)

if __name__=='__main__':run()
