"""Resource workload bounds valid beyond the restricted relay-mode catalogue."""
import math
from fractions import Fraction as F
import pandas as pd
from src.bench_p1.common import ROOT,write,digest
from src.common.charging import charge_time_s

OUT=ROOT/'results/p1_3a'
def down(x):return math.nextafter(float(x),-math.inf)
def main():
    data=ROOT/'data/processed'
    types=pd.read_csv(data/'transport_uav_types.csv').set_index('uav_type')
    bats=pd.read_csv(data/'transport_batteries.csv').set_index('uav_type')
    uavs=pd.read_csv(data/'transport_uavs.csv');records=[]
    for pid in ('A11','AN01','A03'):
        path=OUT/'admission/q2/pareto_schedules'/pid/'q2_sorties.csv'
        flights=pd.read_csv(path,float_precision='round_trip');rows=[];bounds=[]
        single=max(F.from_float(float(r.return_s))-F.from_float(float(r.preparation_start_s)) for r in flights.itertuples())
        bounds.append(single)
        for typ,g in flights.groupby('uav_type'):
            n=int((uavs.uav_type==typ).sum());m=int(bats.loc[typ].battery_pool_count)
            workload=sum((F.from_float(float(r.return_s))-F.from_float(float(r.preparation_start_s)) for r in g.itertuples()),F(0))
            charges=[charge_time_s(1-float(r.energy_kwh)/types.loc[typ].battery_energy_kwh,bats.loc[typ].full_charge_time_s) for r in g.itertuples()]
            battery=sum((F.from_float(float(r.return_s))-F.from_float(float(r.takeoff_s))+F.from_float(float(c)) for r,c in zip(g.itertuples(),charges)),F(0))
            uav_bound=workload/n;battery_bound=battery/m-F.from_float(max(charges));bounds.extend([uav_bound,battery_bound])
            rows.append(dict(type=typ,uavs=n,batteries=m,uav_workload_s=float(workload),
                    uav_workload_lower_bound_s=down(uav_bound),battery_workload_lower_bound_s=down(battery_bound),
                    uav_bound_rational=dict(numerator=str(uav_bound.numerator),denominator=str(uav_bound.denominator))))
        best=max(bounds)
        records.append(dict(pid=pid,input_sha256=digest(path),individual_duration_lower_bound_s=down(single),typed_resource_bounds=rows,
             universal_fixed_transport_makespan_lower_bound_s=down(best),
             scope='ANY_Q3_SCHEDULE_WITH_THIS_TRANSPORT_BOX_VISIT_TYPE_STRUCTURE_AND_ORIGINAL_RESOURCES; INDEPENDENT_OF_RELAY_CATALOGUE_OR_EVENT_ORDERS',
             derivation='UAV: sum(return-preparation) <= count*T. Battery: sum(return+charge-takeoff) <= pool*(T+max_charge). Individual: T >= return-preparation.',
             does_not_bound_entire_transport_pattern_pool=True))
    write(OUT/'transport_resource_lower_bounds.json',records)
    print('TRANSPORT_RESOURCE_BOUNDS',[(r['pid'],r['universal_fixed_transport_makespan_lower_bound_s']) for r in records])

if __name__=='__main__':main()
