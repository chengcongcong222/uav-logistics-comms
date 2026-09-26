"""Build explicit numeric figure inputs from admitted autonomous sources."""
from pathlib import Path
import ast,json,hashlib
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'results/p1_5b';DATA=OUT/'figure_data'
PKG=ROOT/'results/p1_5a/execution/q3/F13/solutions/F13_C2_SITE_B6500_RELAY_00_Q3'
def read(p):return json.loads(p.read_text())
def write(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
def main():
    DATA.mkdir(exist_ok=True);geo=ROOT/'results/reset/geometry'
    def copyframe(src,name):
        p=DATA/name;p.write_bytes(src.read_bytes());return pd.read_csv(p,float_precision='round_trip')
    copyframe(geo/'nodes.csv','nodes.csv')
    for stem in ['transport_sorties','box_delivery','transport_uav_calendar','transport_battery_calendar','relay_sorties','relay_uav_calendar','relay_energy_calendar','communication_guarantee']:
        copyframe(PKG/f'{stem}_F13.csv',stem+'.csv')
    copyframe(PKG/'guarded_atomic_tasks.csv','original_gaps.csv')
    comps=read(OUT/'admitted_comparators.json')
    pd.DataFrame([dict(id=x['id'],**x['metrics']) for x in comps]).to_csv(DATA/'tradeoffs.csv',index=False)
    copyframe(OUT/'q1_sensitivity/figure_source.csv','q1_levels.csv')
    copyframe(OUT/'q1_sensitivity/payload_by_margin.csv','q1_payload.csv')
    q4=read(ROOT/'results/p1_5a/q4/independent_validation.json')
    cfg=read(ROOT/'results/p1_5a/q4/config.json');rows=[];groups=[]
    for x in q4['representatives']:
        role='缺口优先' if x['partition_id'] in cfg['selected'] else '均衡优先'
        rows.append(dict(id=x['partition_id'],k=x['k'],role=role,shortage=x['total_shortage_units'],cv=x['workload_cv'],**x['shortage']))
        for group in x['groups']:
            for svc in group['services']:groups.append(dict(id=x['partition_id'],k=x['k'],role=role,group=group['group_id'],service=svc))
    pd.DataFrame(rows).to_csv(DATA/'q4_tradeoff.csv',index=False);pd.DataFrame(groups).to_csv(DATA/'q4_groups.csv',index=False)
    types=pd.read_csv(geo/'transport_uav_types.csv').set_index('uav_type');g=pd.read_csv(geo/'route_geometry.csv').set_index(['from_id','to_id'])
    curves=[]
    for typ,p in types.iterrows():
        for mass in np.linspace(0,p.max_payload_kg,81):
            e=0.
            for a,b,q in [('O01','S004',mass),('S004','O01',0.)]:
                z=g.loc[a,b];R=p.range_empty_m-(p.range_empty_m-p.range_full_m)*(q/p.max_payload_kg)**1.5
                e+=p.battery_energy_kwh*z.horizontal_distance_m/R+(p.empty_mass_with_battery_kg+q)*9.80665*z.climb_height_m/(p.climb_energy_eff*3.6e6)
            curves.append(dict(type=typ,mass_kg=mass,energy_kwh=e,budget_kwh=.8*p.battery_energy_kwh))
    pd.DataFrame(curves).to_csv(DATA/'payload_energy_curve.csv',index=False)
    metadata=dict(patterns=2903,single_stop=296,two_stop=2607,classes=61,selected_transport=24,
        geometry_example=g.loc['O01','S004'].to_dict(),source_service='S004',
        semantics='Transport blue; relay orange; terrain/resource boundaries neutral gray')
    write(DATA/'mechanism.json',metadata)
    summary=read(OUT/'q1_sensitivity/summary.json')
    catalog=pd.read_csv(OUT/'q1_sensitivity/all_capacity_feasible_subsets.csv')
    bymargin=pd.concat([catalog[catalog.reserve_limit>=rho-1e-10].assign(rho=rho) for rho in [.1,.15,.2,.25,.3]],ignore_index=True)
    bymargin.to_csv(OUT/'q1_sensitivity/feasible_packing_candidates.csv',index=False)
    write(DATA/'q1_breakpoints.json',summary['count_breakpoints'])
    print('FIGURE_INPUTS',len(list(DATA.iterdir())),flush=True)
if __name__=='__main__':main()
