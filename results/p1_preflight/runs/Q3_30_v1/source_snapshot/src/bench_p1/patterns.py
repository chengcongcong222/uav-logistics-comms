"""P1 isolated preference-aware fork of G2 patterns; physics unchanged.

No XB or supplied R structure is read by this module. Material classes retain
destination, mass, volume, hard/expected deadline and priority equivalence.
"""
import argparse,hashlib,itertools,json,math,time
from collections import defaultdict
import numpy as np
import pandas as pd
from scipy.optimize import milp,Bounds,LinearConstraint
from scipy.sparse import coo_matrix
from src.reset.geometry import ROOT,OUT,DATA,tables,write,VERSION
from src.q2.evaluator import MissionEvaluator
from src.common.charging import charge_time_s
from src.q3.e6_resources import color_intervals
from src.xb1.audit import export

def build_pool():
    t=tables();boxes=t['boxes'];ev=MissionEvaluator(t);classes=defaultdict(list)
    for b in boxes.sort_values('box_id').itertuples():
        hd=ev.hard_deadline(b.box_id)
        key=(b.service_id,float(b.mass_kg),float(b.volume_m3),hd if hd is not None else -1.,float(b.expected_deadline_s),float(b.priority_weight))
        classes[key].append(b.box_id)
    keys=sorted(classes);groups=[classes[k] for k in keys];by=defaultdict(list)
    for i,k in enumerate(keys):by[k[0]].append(i)
    geom=t['geom'].set_index(['from_id','to_id']);battery=t['batteries'].set_index('uav_type');types=t['types']
    def physical(counts,seq,typ):
        p=types.loc[typ];n=sum(counts.values());mass=sum(keys[c][1]*v for c,v in counts.items());volume=sum(keys[c][2]*v for c,v in counts.items())
        if mass>p.max_payload_kg+1e-9 or volume>p.cargo_volume_m3+1e-9:return None
        prep=p.prep_time_s+n*p.load_time_per_box_s;clock=prep;energy=0.;q=mass;deliver={}
        path=['O01']+seq+['O01']
        for a,b in zip(path[:-1],path[1:]):
            g=geom.loc[a,b];L=p.range_empty_m-(p.range_empty_m-p.range_full_m)*(q/p.max_payload_kg)**1.5
            energy+=p.battery_energy_kwh*g.horizontal_distance_m/L+(p.empty_mass_with_battery_kg+q)*9.80665*g.climb_height_m/(p.climb_energy_eff*3.6e6)
            clock+=g.climb_height_m/p.max_climb_mps+g.horizontal_distance_m/p.cruise_speed_mps+g.descent_height_m/p.max_descend_mps
            if b!='O01':
                cids=[c for c in counts if keys[c][0]==b];clock+=p.handover_base_s+sum(counts[c] for c in cids)*p.handover_per_box_s
                for c in cids:deliver[c]=clock
                q-=sum(counts[c]*keys[c][1] for c in cids)
        if energy>.8*p.battery_energy_kwh+1e-9:return None
        hard=min([keys[c][3]-deliver[c] for c in counts if keys[c][3]>=0]+[40000.])
        if hard<0:return None
        return dict(type=typ,counts=sorted(counts.items()),sequence=seq,n=n,mass=mass,volume=volume,energy=energy,prep=prep,duration=clock,delivery={str(c):v for c,v in deliver.items()},hard_latest=hard,zero_latest=min(keys[c][4]-deliver[c] for c in counts),charge=charge_time_s(1-energy/p.battery_energy_kwh,battery.loc[typ].full_charge_time_s))
    allpatterns=[];tick=time.monotonic()
    for svc,cids in sorted(by.items()):
        for vector in itertools.product(*[range(len(groups[c])+1) for c in cids]):
            counts={c:v for c,v in zip(cids,vector) if v}
            if not counts:continue
            for typ in types.index:
                p=physical(counts,[svc],typ)
                if p:allpatterns.append(p)
    keep=set();local_logs=[]
    for svc,cids in sorted(by.items()):
        for allowed in ['ABC','A','B','C']:
            inds=[i for i,p in enumerate(allpatterns) if p['sequence']==[svc] and p['type'] in allowed]
            if not inds:continue
            matrix=np.array([[dict(allpatterns[i]['counts']).get(c,0) for i in inds] for c in cids]);dem=[len(groups[c]) for c in cids]
            for objective in ['energy','count','duration','battery']:
                cost=[allpatterns[i]['energy'] if objective=='energy' else 1000+allpatterns[i]['energy'] if objective=='count' else allpatterns[i]['duration']+(allpatterns[i]['charge'] if objective=='battery' else 0) for i in inds]
                sol=milp(cost,integrality=np.ones(len(inds)),bounds=Bounds(0,16),constraints=LinearConstraint(matrix,dem,dem),options=dict(time_limit=.3))
                if sol.x is not None:keep.update(inds[j] for j,v in enumerate(sol.x) if v>.5)
                local_logs.append(dict(service=svc,types=allowed,objective=objective,status=int(sol.status)))
    keep.update(i for i,p in enumerate(allpatterns) if p['n']==1)
    patterns=[allpatterns[i] for i in sorted(keep)];single_count=len(patterns)
    # Deliberately bounded multi-stop proposal pool. Enumerate every type and
    # both orientations for selected neighboring load pairs, not list-prefix types.
    nodes=t['nodes'].set_index('node_id');neighbors=set()
    for svc in by:
        others=sorted((s for s in by if s!=svc),key=lambda s:(nodes.loc[s].x_m-nodes.loc[svc].x_m)**2+(nodes.loc[s].y_m-nodes.loc[svc].y_m)**2)
        neighbors.update(tuple(sorted([svc,s])) for s in others[:3])
    seen=set()
    for a,b in sorted(neighbors):
        aa=[p for p in patterns[:single_count] if p['sequence']==[a]];bb=[p for p in patterns[:single_count] if p['sequence']==[b]]
        def loads(ps):
            selected=sorted(ps,key=lambda p:(-p['n'],p['energy']))[:6]+sorted(ps,key=lambda p:(p['mass'],p['energy']))[:4]
            return {tuple(map(tuple,p['counts'])):p for p in selected}.values()
        for pa,pb in itertools.product(loads(aa),loads(bb)):
            counts=dict(pa['counts']+pb['counts'])
            for typ in types.index:
                for seq in [[a,b],[b,a]]:
                    sig=(tuple(sorted(counts.items())),typ,tuple(seq))
                    if sig in seen:continue
                    seen.add(sig);p=physical(counts,seq,typ)
                    if p:patterns.append(p)
    result=dict(geometry=VERSION,classes=[dict(key=k,boxes=groups[i]) for i,k in enumerate(keys)],patterns=patterns,single_stop_full_count=len(allpatterns),single_stop_retained=single_count,multi_stop_retained=len(patterns)-single_count,complete_pool=False,generation_runtime_s=time.monotonic()-tick,local_selection_logs=local_logs,inputs_read=[str(DATA/'route_geometry.csv')]+[str(ROOT/'data/processed'/f) for f in ['boxes.csv','nodes.csv','transport_uav_types.csv','transport_uavs.csv','transport_batteries.csv']],no_external_structure_inputs=True)
    write(OUT/'pattern_pool.json',result);print('POOL',len(allpatterns),single_count,len(patterns),flush=True);return result

def solve(pool,pid,horizon=7200,step=180,limit=60,zero=True,single=False,challenge=None,preference=None):
    patterns=pool['patterns'];classes=pool['classes'];nclasses=len(classes);t=tables();types=t['types'];battery=t['batteries'].set_index('uav_type');nslots=math.ceil((horizon+5000)/step)
    inv={g:len(t['uavs'][t['uavs'].uav_type==g]) for g in 'ABC'};rows=[];cols=[];vals=[];meta=[];cost=[];bound=[];column_metrics=[]
    for i,p in enumerate(patterns):
        if single and len(p['sequence'])>1:continue
        latest=min(p['hard_latest'],horizon-p['duration'],p['zero_latest'] if zero else horizon)
        for st in range(max(0,math.floor(latest/step)+1)):
            s=st*step;j=len(cost);gi='ABC'.index(p['type'])
            late=sum(v*classes[c]['key'][5]*max(0,s+p['delivery'][str(c)]-classes[c]['key'][4]) for c,v in p['counts'])
            norm=sum(v*classes[c]['key'][5]*(s+p['delivery'][str(c)])/classes[c]['key'][4] for c,v in p['counts'])
            for c,v in p['counts']:rows.append(c);cols.append(j);vals.append(v)
            for k in range(st,math.ceil((s+p['duration'])/step-1e-12)):rows.append(nclasses+gi*nslots+k);cols.append(j);vals.append(1)
            for k in range(math.floor((s+p['prep'])/step+1e-12),math.ceil((s+p['duration']+p['charge'])/step-1e-12)):rows.append(nclasses+3*nslots+gi*nslots+k);cols.append(j);vals.append(1)
            cost.append(p['energy']);bound.append(min(inv[p['type']],min(len(classes[c]['boxes'])//v for c,v in p['counts'])));meta.append((i,s));column_metrics.append((late,norm,p['energy'],1))
    nr=nclasses+6*nslots;dem=[len(c['boxes']) for c in classes];lo=dem+[-np.inf]*(6*nslots);hi=dem+[inv[g] for g in 'ABC' for _ in range(nslots)]+[int(battery.loc[g].battery_pool_count) for g in 'ABC' for _ in range(nslots)]
    if challenge:
        den=sum(len(c['boxes'])*c['key'][5] for c in classes)
        for axis,cap in [(0,challenge['J_late']+1e-7),(1,challenge['J_norm']*den+1e-7),(2,challenge['energy']+1e-8),(3,challenge['sorties'])]:
            for j,m in enumerate(column_metrics):rows.append(nr);cols.append(j);vals.append(m[axis])
            lo.append(-np.inf);hi.append(cap);nr+=1
        cost=[-sum((cap-v)/scale for cap,v,scale in zip([0,0,0,0],m,[1000,1000,10,10])) for m in column_metrics]
    integrality=[1]*len(cost)
    if preference is not None:
        den=sum(len(c['boxes'])*c['key'][5] for c in classes)
        w=preference.weight;scl=preference.scales
        cost=[w[0]*v[1]/den/scl[0]+w[2]*v[2]/scl[2]+w[3]*v[3]/scl[3] for v in column_metrics]
        tv=len(cost);cost.append(w[1]/scl[1]);bound.append(horizon);integrality.append(0)
        for j,(pi,start) in enumerate(meta):
            end=start+patterns[pi]['duration']
            if bound[j]==1:used=j
            else:
                used=len(cost);cost.append(0.);bound.append(1);integrality.append(1)
                rows.extend([nr,nr]);cols.extend([j,used]);vals.extend([1,-bound[j]]);lo.append(-np.inf);hi.append(0);nr+=1
            rows.extend([nr,nr]);cols.extend([used,tv]);vals.extend([end,-1]);lo.append(-np.inf);hi.append(0);nr+=1
        preference.event('milp_objective',horizon_s=horizon,zero_lateness=zero,objective_coefficients_sha256=hashlib.sha256(np.array(cost).tobytes()).hexdigest(),transport_makespan_epigraph=True,variables=len(cost))
    matrix=coo_matrix((vals,(rows,cols)),shape=(nr,len(cost))).tocsc();tick=time.monotonic()
    sol=milp(np.array(cost),integrality=np.array(integrality),bounds=Bounds(np.zeros(len(cost)),bound),constraints=LinearConstraint(matrix,lo,hi),options=dict(time_limit=limit,mip_rel_gap=.01,presolve=False))
    info=dict(pid=pid,status=int(sol.status),message=sol.message,wall_s=time.monotonic()-tick,time_limit_s=limit,horizon_s=horizon,start_grid_s=step,zero_lateness=zero,single_stop_only=single,patterns_available=len(patterns),variables=len(cost),geometry=VERSION,global_optimum_proven=False,incumbent_continuous_schedule_not_guaranteed_in_grid_domain=challenge is not None)
    if sol.x is None:write(OUT/'search_logs'/f'{pid}.json',info);print('NO_WITNESS',pid,info,flush=True);return None
    info.update(objective=float(sol.fun),restricted_dual_bound=float(sol.mip_dual_bound),restricted_mip_gap=float(sol.mip_gap));remaining={i:list(c['boxes']) for i,c in enumerate(classes)};missions=[];ev=MissionEvaluator(t)
    for j,v in enumerate(sol.x[:len(meta)]):
        for _ in range(int(round(v))):
            pi,s=meta[j];p=patterns[pi];by=defaultdict(list)
            for c,n in p['counts']:
                for _ in range(n):by[classes[c]['key'][0]].append(remaining[c].pop(0))
            m=ev.evaluate_mission(p['type'],dict(by),p['sequence']);assert m
            assert abs(m.energy_kwh-p['energy'])<1e-7
            m.mission_id=f'M{len(missions)+1:03d}';m.preparation_start_s=s;m.takeoff_s=s+m.relative_takeoff_time;m.return_s=s+m.relative_return_time;m.delivery_times_s={a:s+b for a,b in m.relative_delivery_times.items()};missions.append(m)
    assert not any(remaining.values())
    for g in 'ABC':
        mm=[m for m in missions if m.uav_type==g]
        for kind in ['uav','battery']:
            intervals=[dict(i=i,start=m.preparation_start_s if kind=='uav' else m.takeoff_s,end=m.return_s+(0 if kind=='uav' else charge_time_s(1-m.energy_kwh/types.loc[g].battery_energy_kwh,battery.loc[g].full_charge_time_s))) for i,m in enumerate(mm)]
            ids=list(t['uavs'][t['uavs'].uav_type==g].uav_id) if kind=='uav' else [f'BAT-{g}-{i:02d}' for i in range(1,int(battery.loc[g].battery_pool_count)+1)]
            color_intervals(intervals,'start','end',ids,'rid')
            for r in intervals:setattr(mm[r['i']],kind+'_id',r['rid'])
    # Continuous earliest left shift in the found UAV and battery orders.
    edges=[]
    for kind in ['uav','battery']:
        for rid in sorted({getattr(m,kind+'_id') for m in missions}):
            mm=sorted([m for m in missions if getattr(m,kind+'_id')==rid],key=lambda m:m.preparation_start_s if kind=='uav' else m.takeoff_s)
            for a,b in zip(mm[:-1],mm[1:]):
                gap=a.relative_return_time
                if kind=='battery':gap+=charge_time_s(1-a.energy_kwh/types.loc[a.uav_type].battery_energy_kwh,battery.loc[a.uav_type].full_charge_time_s)-b.relative_takeoff_time
                edges.append((a.mission_id,b.mission_id,gap+1e-5))
    starts={m.mission_id:0. for m in missions}
    for _ in range(len(missions)+1):
        changed=False
        for a,b,d in edges:
            if starts[b]<starts[a]+d-1e-8:starts[b]=starts[a]+d;changed=True
        if not changed:break
    assert not changed
    for m in missions:
        s=starts[m.mission_id];m.preparation_start_s=s;m.takeoff_s=s+m.relative_takeoff_time;m.return_s=s+m.relative_return_time;m.delivery_times_s={a:s+b for a,b in m.relative_delivery_times.items()}
    metrics=export(missions,t,OUT/'q2/pareto_schedules'/pid,pid);info['metrics']=metrics
    write(OUT/'search_logs'/f'{pid}.json',info);print('SOLVED',pid,metrics,flush=True);return metrics

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--build',action='store_true');ap.add_argument('--pid');ap.add_argument('--horizon',type=int,default=7200);ap.add_argument('--step',type=int,default=180);ap.add_argument('--limit',type=float,default=60);ap.add_argument('--soft',action='store_true');ap.add_argument('--single',action='store_true');args=ap.parse_args()
    pool=build_pool() if args.build else json.loads((OUT/'pattern_pool.json').read_text())
    if args.pid:solve(pool,args.pid,args.horizon,args.step,args.limit,not args.soft,args.single)
