"""Five G2 reserve levels; independent scalar physics and set-partition MILP."""
import ast,itertools,json,math,time
from functools import lru_cache
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.optimize import milp,Bounds,LinearConstraint
from src.q1.solve_q1 import solve_q1,max_safe_payload
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'results/p1_5b/q1_sensitivity'
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def main():
    base=ROOT/'results/reset/geometry'
    types=pd.read_csv(base/'transport_uav_types.csv').set_index('uav_type')
    boxes=pd.read_csv(base/'boxes.csv');geo=pd.read_csv(base/'route_geometry.csv',float_precision='round_trip');gg=geo.set_index(['from_id','to_id'])
    def physical(typ,svc,mass,n):
        p=types.loc[typ];e=0.;t=p.prep_time_s+n*p.load_time_per_box_s+p.handover_base_s+n*p.handover_per_box_s
        for a,b,q in [('O01',svc,mass),(svc,'O01',0.)]:
            g=gg.loc[a,b];R=p.range_empty_m-(p.range_empty_m-p.range_full_m)*(q/p.max_payload_kg)**1.5
            e+=p.battery_energy_kwh*g.horizontal_distance_m/R+(p.empty_mass_with_battery_kg+q)*9.80665*g.climb_height_m/(p.climb_energy_eff*3.6e6)
            t+=g.horizontal_distance_m/p.cruise_speed_mps+g.climb_height_m/p.max_climb_mps+g.descent_height_m/p.max_descend_mps
        return float(e),float(t)
    allcand={};catalog=[]
    for svc,items in boxes.groupby('service_id',sort=True):
        items=items.reset_index(drop=True);rows=[]
        for mask in range(1,1<<len(items)):
            ids=[i for i in range(len(items)) if mask>>i&1];batch=items.iloc[ids];mass=float(batch.mass_kg.sum());vol=float(batch.volume_m3.sum())
            for typ,p in types.iterrows():
                if mass>p.max_payload_kg+1e-9 or vol>p.cargo_volume_m3+1e-9:continue
                e,t=physical(typ,svc,mass,len(ids))
                row=dict(service_id=svc,uav_type=typ,mask=mask,box_ids=batch.box_id.tolist(),mass_kg=mass,volume_m3=vol,energy_kwh=e,time_s=t,reserve_limit=1-e/p.battery_energy_kwh)
                rows.append(row);catalog.append(row)
        allcand[svc]=(items,rows)
    pd.DataFrame(catalog).to_csv(OUT/'all_capacity_feasible_subsets.csv',index=False)
    payload=[];packs=[];summaries=[];valid=[];feasiblecounts=[];per_service=[]
    for rho in [.1,.15,.2,.25,.3]:
        limits=[dict(rho=rho,**max_safe_payload(types,geo,typ,svc,rho)) for typ in types.index for svc in sorted(allcand)]
        payload+=limits
        for r in limits:
            p=types.loc[r['uav_type']];e,_=physical(r['uav_type'],r['service_id'],r['payload_limit_kg'],0)
            assert abs(e-r['roundtrip_energy_kwh'])<1e-8
            if r['binding_constraint']=='energy_infeasible_even_empty':assert e>(1-rho)*p.battery_energy_kwh
            else:
                assert e<=(1-rho)*p.battery_energy_kwh+1e-8
                if r['binding_constraint']=='energy':assert physical(r['uav_type'],r['service_id'],r['payload_limit_kg']+1e-5,0)[0]>(1-rho)*p.battery_energy_kwh
        fl=solve_q1(types,geo,boxes,rho);packs.extend(fl.to_dict('records'));seen=[]
        for r in fl.itertuples():
            ids=r.box_ids;seen+=ids;batch=boxes.set_index('box_id').loc[ids]
            assert set(batch.service_id)=={r.service_id}
            e,t=physical(r.uav_type,r.service_id,float(batch.mass_kg.sum()),len(ids))
            assert abs(e-r.energy_kwh)<1e-8 and abs(t-r.time_s)<1e-6
            assert e<=(1-rho)*types.loc[r.uav_type].battery_energy_kwh+1e-8
        assert len(seen)==len(set(seen))==80
        for svc,(items,cs) in allcand.items():
            available=[r for r in cs if r['reserve_limit']>=rho-1e-10]
            feasiblecounts.append(dict(rho=rho,service_id=svc,feasible_type_subset_pairs=len(available),feasible_subsets=len({r['mask'] for r in available})))
            A=np.array([[int(r['mask']>>i&1) for r in available] for i in range(len(items))],float)
            sol=milp(np.ones(len(available)),integrality=np.ones(len(available)),bounds=Bounds(0,1),constraints=LinearConstraint(A,1,1),options={'mip_rel_gap':0.})
            assert sol.status==0
            nf=round(sol.fun);sel=fl[fl.service_id==svc];assert nf==len(sel)
            sol2=milp(np.array([r['energy_kwh'] for r in available]),integrality=np.ones(len(available)),bounds=Bounds(0,1),
                constraints=[LinearConstraint(A,1,1),LinearConstraint(np.ones((1,len(available))),nf,nf)],options={'mip_rel_gap':0.})
            assert sol2.status==0 and abs(sol2.fun-sel.energy_kwh.sum())<1e-6
            per_service.append(dict(rho=rho,service_id=svc,sorties=len(sel),energy_kwh=float(sel.energy_kwh.sum()),sum_duration_s=float(sel.time_s.sum()),
                type_counts=sel.uav_type.value_counts().to_dict(),box_groups=[dict(type=r.uav_type,boxes=sorted(r.box_ids)) for r in sel.itertuples()]))
            valid.append(dict(rho=rho,service_id=svc,count_optimum=nf,independent_energy_optimum=sol2.fun,count_bound=sol.mip_dual_bound,energy_bound=sol2.mip_dual_bound,status='OPTIMAL_IN_COMPLETE_SINGLE_SERVICE_SUBSET_DOMAIN'))
        summaries.append(dict(rho=rho,sorties=len(fl),energy_kwh=float(fl.energy_kwh.sum()),sum_duration_s=float(fl.time_s.sum()),type_counts={t:int((fl.uav_type==t).sum()) for t in types.index}))
        print('Q1',summaries[-1],flush=True)
    # Enumerate exact energy thresholds; report discrete changes of the optimum count.
    critical=[]
    for svc,(items,cs) in allcand.items():
        full=(1<<len(items))-1
        def optimum(rho):
            available=[r for r in cs if r['reserve_limit']>=rho-1e-10]
            @lru_cache(None)
            def dp(mask):
                if not mask:return (0,0.,0.)
                low=mask&-mask;vals=[]
                for r in available:
                    sub=r['mask']
                    if sub&low and sub&mask==sub:
                        other=dp(mask^sub)
                        if other:vals.append((other[0]+1,other[1]+r['energy_kwh'],other[2]+r['time_s']))
                return min(vals) if vals else None
            return dp(full)
        for rho in sorted(set(r['reserve_limit'] for r in cs if .1<=r['reserve_limit']<=.3)):
            at=optimum(rho);after=optimum(rho+1e-8)
            if (at[0] if at else None)!=(after[0] if after else None):
                critical.append(dict(service_id=svc,rho_boundary=rho,count_at_boundary=at[0] if at else None,count_just_above=after[0] if after else None,
                    binding_subsets=[dict(uav_type=r['uav_type'],box_ids=r['box_ids']) for r in cs if abs(r['reserve_limit']-rho)<1e-12],
                    boundary_semantics='energy equality feasible; +1e-8 reserve used above the boundary'))
    transitions=[]
    for a,b in zip([.1,.15,.2,.25],[.15,.2,.25,.3]):
        for svc in allcand:
            x=next(r for r in per_service if r['rho']==a and r['service_id']==svc)
            y=next(r for r in per_service if r['rho']==b and r['service_id']==svc)
            if x['box_groups']!=y['box_groups']:
                transitions.append(dict(from_rho=a,to_rho=b,service_id=svc,sorties_before=x['sorties'],sorties_after=y['sorties'],before=x['box_groups'],after=y['box_groups']))
    pd.DataFrame(payload).to_csv(OUT/'payload_by_margin.csv',index=False)
    pd.DataFrame(packs).to_csv(OUT/'packing_by_margin.csv',index=False)
    pd.DataFrame(feasiblecounts).to_csv(OUT/'feasible_subsets_by_margin.csv',index=False)
    pd.DataFrame([dict(rho=x['rho'],sorties=x['sorties'],energy_kwh=x['energy_kwh'],sum_duration_s=x['sum_duration_s'],**{f'sorties_{t}':x['type_counts'][t] for t in types.index}) for x in summaries]).to_csv(OUT/'figure_source.csv',index=False)
    baseline=pd.read_csv(ROOT/'results/reset/q1/q1_packings_rho20.csv',float_precision='round_trip')
    current=pd.DataFrame(packs);current=current[current.rho==.2]
    assert len(current)==len(baseline) and abs(current.energy_kwh.sum()-baseline.energy_kwh.sum())<1e-8
    assert {(r.service_id,r.uav_type,tuple(sorted(r.box_ids))) for r in current.itertuples()}=={(r.service_id,r.uav_type,tuple(sorted(ast.literal_eval(r.box_ids)))) for r in baseline.itertuples()}
    write(OUT/'summary.json',dict(geometry='G2',levels=summaries,per_service=per_service,grid_changes=transitions,count_breakpoints=critical,
        objective='Minimum single-service sortie count, then total energy, then cumulative task duration',scope='Q1 independent per-service grouping; no fleet concurrency or communication; cumulative duration is not makespan'))
    write(OUT/'validation.json',dict(status='PASSED',payload_cases=225,packing_boxes_each_level=80,independent_milp_certificates=valid,baseline_rho20_identical=True,
        independent_physics=True,old_geometry_sensitivity_read=False,critical_boundary_numerics='Exact candidate energy thresholds with 1e-8 one-sided probe'))
if __name__=='__main__':main()
