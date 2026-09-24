"""Export E6 schedules and metrics; independent validation is a separate step."""
from collections import Counter
import json
import numpy as np

from src.q3.e6_resources import *


def export_plan(pid):
    status=json.loads((OUT/f'plan_status_{pid}.json').read_text())
    if status['status']=='FIXED_TRANSPORT_STRUCTURE_INFEASIBLE_UNDER_CURRENT_SEARCH':return
    selected=json.loads((OUT/f'selected_sorties_{pid}.json').read_text())
    shifts=json.loads((OUT/f'shifts_{pid}.json').read_text())
    pair=read(OUT/f'guarded_selected_pairs_{pid}.csv').set_index(['atomic_task_id','site_id'])
    atoms=read(OUT/'guarded_atomic_tasks.csv').set_index('atomic_task_id')
    base=RESULTS_Q2/'pareto_schedules'/pid
    transport=read(base/'q2_sorties.csv')
    for col in ['preparation_start_s','takeoff_s','return_s']:
        transport[col]=transport[col]+transport.sortie_id.map(shifts)
    deliveries=read(base/'q2_box_delivery.csv')
    deliveries.delivery_time_s+=deliveries.sortie_id.map(shifts)
    deliveries.hard_deadline_ok=deliveries.hard_deadline_s.isna()|(deliveries.delivery_time_s<=deliveries.hard_deadline_s+1e-6)
    deliveries.normalized_delivery_time=deliveries.delivery_time_s/deliveries.expected_deadline_s
    write_csv(OUT/f'transport_sorties_{pid}.csv',transport.to_dict('records'))
    write_csv(OUT/f'box_delivery_{pid}.csv',deliveries.to_dict('records'))
    write_csv(OUT/f'transport_shifts_{pid}.csv',[dict(sortie_id=s,shift_s=v) for s,v in shifts.items()])
    write_csv(OUT/f'transport_uav_calendar_{pid}.csv',[
        dict(uav_id=r.uav_id,sortie_id=r.sortie_id,busy_start_s=r.preparation_start_s,busy_end_s=r.return_s) for r in transport.itertuples()])
    types=read(PROCESSED_DIR/'transport_uav_types.csv').set_index('uav_type')
    bat=read(PROCESSED_DIR/'transport_batteries.csv').set_index('uav_type')
    battery=[]
    for r in transport.itertuples():
        soc=1-r.energy_kwh/types.loc[r.uav_type].battery_energy_kwh
        charge=charge_time_s(soc,bat.loc[r.uav_type].full_charge_time_s)
        battery.append(dict(battery_id=r.battery_id,sortie_id=r.sortie_id,takeoff_s=r.takeoff_s,return_s=r.return_s,
                            return_soc=soc,energy_ready_s=r.return_s+charge,charge_duration_s=charge))
    write_csv(OUT/f'transport_battery_calendar_{pid}.csv',battery)
    flat=[];uav=[];components=[];guarantee=[]
    for row in selected:
        r=dict(row);r['task_ids']=json.dumps(r['task_ids']);r['service_windows']=json.dumps(r['service_windows']);flat.append(r)
        uav.append(dict(relay_id=r['relay_id'],relay_sortie_id=r['relay_sortie_id'],busy_start_s=r['preparation_start_s'],
                        return_s=r['return_s'],busy_end_s=r['uav_available_s'],turnaround_s=300.))
        components.append(dict(energy_component_id=r['energy_component_id'],relay_sortie_id=r['relay_sortie_id'],
                               takeoff_s=r['takeoff_s'],return_s=r['return_s'],soc_at_takeoff=1.,return_soc=r['return_soc'],
                               charge_start_s=r['return_s'],charge_end_s=r['energy_ready_s'],charge_duration_s=r['charge_duration_s']))
        for aid in row['task_ids']:
            task=atoms.loc[aid];edge=pair.loc[(aid,row['site_id'])];d=shifts[task.transport_sortie_id]
            guarantee.append(dict(atomic_task_id=aid,parent_gap_id=task.parent_gap_id,transport_sortie_id=task.transport_sortie_id,
                                  service_start_s=task.service_start_s+d,service_end_s=task.service_end_s+d,
                                  relay_sortie_id=r['relay_sortie_id'],relay_id=r['relay_id'],site_id=r['site_id'],
                                  topology='TRANSPORT_RELAY_G01',provider_count=1,
                                  min_access_margin_db=float(edge.min_access_margin_db),backhaul_margin_db=float(edge.backhaul_margin_db),
                                  min_twohop_margin_db=float(edge.min_twohop_margin_db)))
    write_csv(OUT/f'relay_sorties_{pid}.csv',flat)
    write_csv(OUT/f'relay_uav_calendar_{pid}.csv',uav)
    write_csv(OUT/f'relay_energy_calendar_{pid}.csv',components)
    write_csv(OUT/f'communication_guarantee_{pid}.csv',guarantee)
    raw=read(PROCESSED_DIR/'boxes.csv').set_index('box_id')
    w=deliveries.box_id.map(raw.priority_weight).to_numpy();d=deliveries.delivery_time_s.to_numpy()
    deadlines=deliveries.box_id.map(raw.expected_deadline_s).to_numpy()
    relay_energy=sum(r['total_energy_kwh'] for r in selected)
    horizon=max(transport.return_s.max(),max(r['return_s'] for r in selected))
    resource_horizon=max(horizon,max(r['energy_ready_s'] for r in selected),max(r['uav_available_s'] for r in selected))
    ru={}
    for rid in ['R01','R02']:
        rows=[r for r in selected if r['relay_id']==rid]
        ru[rid]=dict(sorties=len(rows),operating_s=sum(r['return_s']-r['preparation_start_s'] for r in rows),
                     unavailable_s=sum(r['uav_available_s']-r['preparation_start_s'] for r in rows),
                     utilization=sum(r['uav_available_s']-r['preparation_start_s'] for r in rows)/resource_horizon)
    ec={}
    for rid in [f'REC-{i:02d}' for i in range(1,7)]:
        rows=[r for r in selected if r['energy_component_id']==rid]
        ec[rid]=dict(sorties=len(rows),unavailable_s=sum(r['energy_ready_s']-r['takeoff_s'] for r in rows),
                     utilization=sum(r['energy_ready_s']-r['takeoff_s'] for r in rows)/resource_horizon)
    metrics=dict(pareto_id=pid,conclusion=status['status'],J_late=float(np.sum(w*np.maximum(0,d-deadlines))),
                 J_norm=float(np.sum(w*d/deadlines)/np.sum(w)),joint_makespan_s=horizon,
                 transport_energy_kwh=float(transport.energy_kwh.sum()),relay_energy_kwh=relay_energy,
                 total_energy_kwh=float(transport.energy_kwh.sum())+relay_energy,
                 transport_sorties=len(transport),relay_sorties=len(selected),total_transport_shift_s=sum(shifts.values()),
                 max_transport_shift_s=max(shifts.values()),hard_deadline_violations=int((~deliveries.hard_deadline_ok).sum()),
                 communication_uncovered_duration_s=None,communication_validation='PENDING_INDEPENDENT_FULL_FLIGHT_AUDIT',
                 minimum_M_E_kwh=min(r['energy_margin_kwh'] for r in selected),
                 minimum_M_C_db=min(r['min_twohop_margin_db'] for r in guarantee),
                 relay_uav_utilization=ru,energy_component_utilization=ec,resource_calendar_horizon_s=resource_horizon,
                 candidate_set_complete=False,one_to_many_relay=True,comm_power_counted_once_per_active_module=True)
    write_json(OUT/f'joint_metrics_{pid}.json',metrics)
    print(pid,metrics['conclusion'],'relay_sorties',len(selected),'shift',metrics['total_transport_shift_s'],flush=True)


if __name__=='__main__':
    for pid in ['P01','P02','P03']:export_plan(pid)
