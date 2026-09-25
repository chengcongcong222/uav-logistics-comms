"""Q2 active dominance MILP; fixed structure, free starts/UAV/battery allocation."""
import copy,json,time
import numpy as np
from scipy.optimize import Bounds,LinearConstraint
from scipy.sparse import coo_matrix
from src.q2.mission import Mission
from src.common.charging import charge_time_s
from src.q3.e6_resources import color_intervals

def challenge(target,tab,milp,rng,preference=None):
    missions=[Mission(**d) for d in json.loads(open(target['mission_file']).read())];rng.shuffle(missions)
    inc=target['metrics'];n=len(missions);boxes=tab['boxes'].set_index('box_id');battery=tab['batteries'].set_index('uav_type')
    deliveries=[(i,s,b) for i,m in enumerate(missions) for s,ids in m.boxes_by_service.items() for b in ids];normden=sum(float(boxes.loc[b].priority_weight) for i,s,b in deliveries)
    size=n+len(deliveries)+1;T=size-1;c=[0.]*size;integ=[0]*size;bounds=[(0,inc['makespan'])]*n+[(0,None)]*len(deliveries)+[(0,inc['makespan']+1e-7)]
    rows=[];lo=[];hi=[];normrow={};normconstant=0.;laterow={};M=50000.
    def add(row,l=-np.inf,h=np.inf):rows.append(row);lo.append(l);hi.append(h)
    def var():j=len(c);c.append(0.);integ.append(1);bounds.append((0,1));return j
    for i,m in enumerate(missions):
        add({i:1,T:-1},h=-m.relative_return_time)
        if m.hard_deadline_latest_start is not None:bounds[i]=(0,m.hard_deadline_latest_start)
    for j,(i,s,b) in enumerate(deliveries):
        box=boxes.loc[b];d=missions[i].relative_delivery_times[s];w=float(box.priority_weight);deadline=float(box.expected_deadline_s)
        add({i:1,n+j:-1},h=deadline-d);laterow[n+j]=w;normrow[i]=normrow.get(i,0)+w/deadline/normden;normconstant+=w*d/deadline/normden
    add(laterow,h=inc['J_late']+1e-7);add(normrow,h=inc['J_norm']-normconstant+1e-10)
    for i,v in normrow.items():c[i]=v
    c[T]=1/max(1,inc['makespan'])
    if preference is not None:
        for i,v in normrow.items():c[i]=v*preference.weight[0]/preference.scales[0]
        c[T]=preference.weight[1]/preference.scales[1]
        preference.event('challenge_objective',fixed_energy_and_sorties=True)
    for kind in ['UAV','BATTERY']:
        for typ in sorted({m.uav_type for m in missions}):
            ids=[i for i,m in enumerate(missions) if m.uav_type==typ];count=len(tab['uavs'][tab['uavs'].uav_type==typ]) if kind=='UAV' else int(battery.loc[typ].battery_pool_count)
            if len(ids)<=count:continue
            assign={i:[var() for _ in range(count)] for i in ids}
            for i in ids:add({v:1 for v in assign[i]},1,1)
            # This symmetry fix permits a type-wise resource relabeling of the incumbent.
            bounds[assign[ids[0]][0]]=(1,1)
            def interval(i):
                m=missions[i];charge=charge_time_s(1-m.energy_kwh/tab['types'].loc[typ].battery_energy_kwh,battery.loc[typ].full_charge_time_s)
                return (0,m.relative_return_time) if kind=='UAV' else (m.relative_takeoff_time,m.relative_return_time+charge)
            for ii,i in enumerate(ids):
                a,b=interval(i)
                for j in ids[ii+1:]:
                    d,e=interval(j);z=var()
                    for r in range(count):
                        add({i:1,j:-1,z:M,assign[i][r]:M,assign[j][r]:M},h=3*M-b+d)
                        add({j:1,i:-1,z:-M,assign[i][r]:M,assign[j][r]:M},h=2*M-e+a)
    rr=[];cc=[];vv=[]
    for i,row in enumerate(rows):
        for j,v in row.items():rr.append(i);cc.append(j);vv.append(v)
    matrix=coo_matrix((vv,(rr,cc)),shape=(len(rows),len(c))).tocsc();tick=time.process_time()
    sol=milp(np.array(c),integrality=integ,bounds=Bounds(*np.array([(a,np.inf if b is None else b) for a,b in bounds]).T),constraints=LinearConstraint(matrix,lo,hi),options=dict(time_limit=14,mip_rel_gap=.001))
    info=dict(status=int(sol.status),solver_cpu_s=time.process_time()-tick,variables=len(c),incumbent_in_domain='yes: original continuous starts/resources, up to symmetry relabeling; no positive separation buffer',domain='fixed box groups/type/visit order; free typed resources and continuous times; all scalar objectives capped',proof='NO_GLOBAL_OR_NONDOMINANCE_PROOF',found_dominator=False)
    if sol.x is None:return None,info
    out=copy.deepcopy(missions)
    for i,m in enumerate(out):
        s=max(0,float(sol.x[i]));m.preparation_start_s=s;m.takeoff_s=s+m.relative_takeoff_time;m.return_s=s+m.relative_return_time;m.delivery_times_s={svc:s+d for svc,d in m.relative_delivery_times.items()}
    for typ in sorted({m.uav_type for m in out}):
        mm=[m for m in out if m.uav_type==typ]
        for kind in ['UAV','BATTERY']:
            rows=[]
            for i,m in enumerate(mm):
                charge=charge_time_s(1-m.energy_kwh/tab['types'].loc[typ].battery_energy_kwh,battery.loc[typ].full_charge_time_s)
                rows.append(dict(i=i,start=m.preparation_start_s if kind=='UAV' else m.takeoff_s,end=m.return_s+(charge if kind=='BATTERY' else 0)))
            pool=list(tab['uavs'][tab['uavs'].uav_type==typ].uav_id) if kind=='UAV' else [f'BAT-{typ}-{j:02d}' for j in range(1,int(battery.loc[typ].battery_pool_count)+1)]
            try:color_intervals(rows,'start','end',pool,'resource')
            except ValueError:return None,dict(info,numerical_resource_coloring_failed=True)
            for row in rows:setattr(mm[row['i']],'uav_id' if kind=='UAV' else 'battery_id',row['resource'])
    late=norm=0.
    for m in out:
        for s,ids in m.boxes_by_service.items():
            for b in ids:
                q=boxes.loc[b];t=m.delivery_times_s[s];late+=q.priority_weight*max(0,t-q.expected_deadline_s);norm+=q.priority_weight*t/q.expected_deadline_s/normden
    makespan=max(m.return_s for m in out)
    improves=(late<inc['J_late']-1e-4 or (abs(late-inc['J_late'])<=1e-4 and norm<inc['J_norm']-1e-9) or makespan<inc['makespan']-1e-6)
    if late>inc['J_late']+1e-4 or norm>inc['J_norm']+1e-9 or makespan>inc['makespan']+1e-6 or not improves:return None,info
    info['found_dominator']=True;return out,info
