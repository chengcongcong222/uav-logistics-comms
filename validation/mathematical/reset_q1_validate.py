"""Independent scalar Q1 physics and maximum-payload boundary checks."""
import ast,json,sys
from pathlib import Path
import pandas as pd
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
OUT=ROOT/'results/reset/q1';DATA=ROOT/'results/reset/geometry'
def validate():
    types=pd.read_csv(DATA/'transport_uav_types.csv').set_index('uav_type')
    geo=pd.read_csv(DATA/'route_geometry.csv').set_index(['from_id','to_id'])
    boxes=pd.read_csv(DATA/'boxes.csv').set_index('box_id');seen=[]
    def physical(typ,svc,mass,n):
        e=0.;duration=typ.prep_time_s+n*typ.load_time_per_box_s+typ.handover_base_s+n*typ.handover_per_box_s
        for a,b,q in [('O01',svc,mass),(svc,'O01',0.)]:
            g=geo.loc[a,b];range_m=typ.range_empty_m-(typ.range_empty_m-typ.range_full_m)*(q/typ.max_payload_kg)**1.5
            e+=typ.battery_energy_kwh*g.horizontal_distance_m/range_m+(typ.empty_mass_with_battery_kg+q)*9.80665*g.climb_height_m/(typ.climb_energy_eff*3.6e6)
            assert typ.descend_energy_eff==0
            duration+=g.horizontal_distance_m/typ.cruise_speed_mps+g.climb_height_m/typ.max_climb_mps+g.descent_height_m/typ.max_descend_mps
        return e,duration
    pk=pd.read_csv(OUT/'q1_packings_rho20.csv')
    for r in pk.itertuples():
        ids=ast.literal_eval(r.box_ids);seen+=ids;batch=boxes.loc[ids];p=types.loc[r.uav_type]
        assert set(batch.service_id)=={r.service_id};mass=batch.mass_kg.sum();volume=batch.volume_m3.sum()
        assert mass<=p.max_payload_kg+1e-8 and volume<=p.cargo_volume_m3+1e-8
        e,t=physical(p,r.service_id,mass,len(ids))
        assert abs(e-r.energy_kwh)<1e-8 and abs(t-r.time_s)<1e-6 and e<=.8*p.battery_energy_kwh+1e-8
        assert abs(mass-r.mass_kg)<1e-8 and abs(volume-r.volume_m3)<1e-8 and len(ids)==r.n_boxes
    assert len(seen)==len(set(seen))==80 and set(seen)==set(boxes.index)
    limits=pd.read_csv(OUT/'max_safe_payload.csv');assert len(limits)==45 and not limits.duplicated(['uav_type','service_id']).any()
    for r in limits.itertuples():
        p=types.loc[r.uav_type];e,_=physical(p,r.service_id,r.payload_limit_kg,0)
        assert abs(e-r.roundtrip_energy_kwh)<1e-8
        if r.binding_constraint=='energy_infeasible_even_empty':assert r.payload_limit_kg==0 and e>.8*p.battery_energy_kwh
        else:
            assert e<=.8*p.battery_energy_kwh+1e-8
            if r.binding_constraint=='mass':assert abs(r.payload_limit_kg-p.max_payload_kg)<1e-8
            else:assert physical(p,r.service_id,r.payload_limit_kg+1e-5,0)[0]>.8*p.battery_energy_kwh
    result=dict(status='G2_Q1_INDEPENDENT_PHYSICS_VERIFIED',boxes=80,sorties=len(pk),payload_limits=45,energy_kwh=float(pk.energy_kwh.sum()),sum_sortie_duration_s=float(pk.time_s.sum()),optimality_scope='generator complete subset DP per service; this independent checker verifies feasibility and payload boundaries, not a second global optimizer')
    (OUT/'validation.json').write_text(json.dumps(result,indent=2)+'\n');print(result)
if __name__=='__main__':validate()
