"""Independent exhaustive audit of the retained expanded E6 candidate edges."""
import argparse,json,time
from e6_validate import *


def audit_pool(pid):
    c=IndependentAudit();tick=time.monotonic()
    pairs=read(OUT/f'candidate_pairs_{pid}.csv')
    sites=read(OUT/f'candidate_sites_{pid}.csv').set_index('site_id')
    atoms=read(Q3/'relay_atomic_tasks_e52.csv').set_index('atomic_task_id')
    results=[];backs={};energies={}
    for i,r in enumerate(pairs.itertuples()):
        a=atoms.loc[r.atomic_task_id];s=sites.loc[r.site_id]
        require(a.pareto_id==pid,'Wrong plan candidate')
        if r.site_id not in backs:
            lon,lat=c.tf.transform(s.x_m,s.y_m);ground=c.dem.sample(lon,lat)
            close(s.ground_elevation_m,ground,'Pool DEM');close(s.z_amsl_m,ground+s.agl_m,'Pool height')
            require(0<s.agl_m<=c.params['max_agl_m'],'Pool height limit')
            backs[r.site_id]=c.backhaul(s)
        access=c.interval((pid,a.transport_sortie_id),s,a.service_start_s,a.service_end_s,step=.5)
        energy=c.energy(s,a.service_end_s-a.service_start_s)
        margin=(1-c.params['rho'])*c.params['energy_kwh']-energy['total_energy_kwh']
        require(min(access,backs[r.site_id],margin)>=-1e-8,f'Invalid candidate {r.atomic_task_id}/{r.site_id}')
        results.append(dict(atomic_task_id=r.atomic_task_id,site_id=r.site_id,min_access_margin_db=access,
                            backhaul_margin_db=backs[r.site_id],energy_margin_kwh=margin))
        if (i+1)%100==0:print(pid,i+1,len(pairs),round(time.monotonic()-tick,2),flush=True)
    pd.DataFrame(results).to_csv(OUT/f'independent_pool_audit_{pid}.csv',index=False)
    result=dict(status='ALL_RETAINED_EXPANDED_PAIRS_VALIDATED',pareto_id=pid,pairs=len(results),sites=len(backs),
                step_s=.5,boundary_refinement_s=.1,link_samples=c.samples,refinement_samples=c.refinements,
                runtime_s=time.monotonic()-tick,candidate_set_complete=False,
                scope='INHERITED_E52_WINDOWS; FINAL_GUARDED_ASSIGNMENTS_AUDITED_SEPARATELY')
    result['artifact_sha256']={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
                              for p in [OUT/f'candidate_pairs_{pid}.csv',OUT/f'candidate_sites_{pid}.csv',Q3/'relay_atomic_tasks_e52.csv']}
    (OUT/f'pool_validation_{pid}.json').write_text(json.dumps(result,indent=2)+'\n')
    print(result,flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--plan',required=True);a=p.parse_args();audit_pool(a.plan)
