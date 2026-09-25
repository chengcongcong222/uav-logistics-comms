"""Independent partition enumeration and event-peak verification."""
import itertools,math
from collections import defaultdict,Counter
import pandas as pd
from src.p1_5a.common import *
KINDS=['TUAV_A','TUAV_B','TUAV_C','TBAT_A','TBAT_B','TBAT_C','RUAV','REC']
def frame(n):return pd.read_csv(PACKAGE/f'{n}_F13.csv',float_precision='round_trip')
def peak(rows):
    events=[]
    for a,b in rows:
        assert b>=a
        events += [(a,1),(b,-1)]
    current=maximum=0
    for _,d in sorted(events,key=lambda x:(x[0],x[1])):
        current+=d;maximum=max(maximum,current)
    assert current==0
    return maximum
def main():
    install_guard();require_admitted()
    q=OUT/'q4';records=read(q/'all_partitions.json');block=read(q/'blocks.json')
    t=frame('transport_sorties');r=frame('relay_sorties');g=frame('communication_guarantee')
    visits={x.sortie_id:set(x.service_sequence.split('>')) for x in t.itertuples()}
    edges=list(visits.values())
    rservices={}
    for rid,gg in g.groupby('relay_sortie_id'):
        rservices[rid]=set().union(*(visits[s] for s in gg.transport_sortie_id))
    edges+=list(rservices.values())
    adjacency={s:set() for s in set().union(*visits.values())}
    for edge in edges:
        for s in edge:adjacency[s]|=edge-{s}
    components=[];remaining=set(adjacency)
    while remaining:
        start=min(remaining);found={start};todo=[start]
        while todo:
            s=todo.pop()
            for v in adjacency[s]-found:found.add(v);todo.append(v)
        remaining-=found;components.append(sorted(found))
    assert sorted(components)==sorted(block['blocks'])
    blocks=block['blocks'];n=len(blocks)
    # Brute force all k^n labelings; canonicalize group permutations independently.
    counts={}
    for k in [2,3]:
        canonical=set()
        for labels in itertools.product(range(k),repeat=n):
            if len(set(labels))!=k:continue
            groups=tuple(sorted(tuple(i for i,v in enumerate(labels) if v==label) for label in range(k)))
            canonical.add(groups)
        saved={tuple(sorted(tuple(i for i,v in enumerate(x['labels']) if v==j) for j in range(k))) for x in records if x['k']==k}
        assert canonical==saved
        counts[str(k)]=len(saved)
    windows=[]
    for x in t.itertuples():windows.append(('TUAV_'+x.uav_type,x.sortie_id,visits[x.sortie_id],x.preparation_start_s,x.return_s))
    types=t.set_index('sortie_id').uav_type.to_dict()
    for x in frame('transport_battery_calendar').itertuples():windows.append(('TBAT_'+types[x.sortie_id],x.sortie_id,visits[x.sortie_id],x.takeoff_s,x.energy_ready_s))
    for x in r.itertuples():
        windows += [('RUAV',x.relay_sortie_id,rservices[x.relay_sortie_id],x.preparation_start_s,x.uav_available_s),('REC',x.relay_sortie_id,rservices[x.relay_sortie_id],x.takeoff_s,x.energy_ready_s)]
    global_need={kind:peak([(a,b) for typ,_,_,a,b in windows if typ==kind]) for kind in KINDS}
    assert global_need==block['global_minimum_resources']
    config=read(q/'config.json');summary=[]
    for x in records:
        service_group={s:group['group_id'] for group in x['groups'] for s in group['services']}
        assert len(service_group)==15 and set(service_group)==set(adjacency)
        assert len(set(service_group.values()))==x['k']
        assert all(len({service_group[s] for s in e})==1 for e in edges)
        totals=Counter();works=[]
        for group in x['groups']:
            rows=[w for w in windows if service_group[next(iter(w[2]))]==group['group_id']]
            need={kind:peak([(a,b) for typ,_,_,a,b in rows if typ==kind]) for kind in KINDS}
            assert need==group['resources'];totals.update(need)
            work=sum(b-a for typ,_,_,a,b in rows if typ.startswith('TUAV') or typ=='RUAV')
            assert abs(work-group['workload_uav_occupied_s'])<1e-6;works.append(work)
        assert dict(totals)==x['resources']
        shortage={kind:max(0,totals[kind]-x['inventory'][kind]) for kind in KINDS}
        surplus={kind:max(0,x['inventory'][kind]-totals[kind]) for kind in KINDS}
        assert shortage==x['shortage'] and surplus==x['inventory_surplus']
        assert sum(shortage.values())==x['total_shortage_units']
        mu=sum(works)/len(works);cv=math.sqrt(sum((v-mu)**2 for v in works)/len(works))/mu
        assert abs(cv-x['workload_cv'])<1e-12
        cal=x['calendar'];by=defaultdict(list)
        assert len(cal)==len(windows)
        expected={(typ,sid):(a,b,service_group[next(iter(ss))]) for typ,sid,ss,a,b in windows}
        for row in cal:
            a,b,gid=expected[row['kind'],row['task_id']]
            assert abs(row['start_s']-a)<1e-8 and abs(row['end_s']-b)<1e-8 and row['group_id']==gid
            assert row['resource_id'].startswith(gid+'-')
            by[row['resource_id']].append((row['start_s'],row['end_s']))
        for rows in by.values():
            rows.sort()
            assert all(a[1]<=b[0]+1e-6 for a,b in zip(rows,rows[1:]))
        if x['partition_id'] in config['selected']+config['balanced_alternatives']:
            summary.append({key:x[key] for key in ['partition_id','k','groups','resources','shortage','inventory_surplus','redundancy','total_shortage_units','workload_cv']})
    for k in [2,3]:
        rr=[x for x in records if x['k']==k]
        best=min(rr,key=lambda x:(x['total_shortage_units'],x['total_resource_units'],x['workload_cv'],x['labels']))
        assert best['partition_id'] in config['selected']
        alt=next(x for x in rr if x['partition_id'] in config['balanced_alternatives'])
        assert abs(alt['workload_cv']-min(x['workload_cv'] for x in rr))<1e-12
    result=dict(status='PASSED',source_solution=IDENT,blocks=n,partitions=counts,all_partitions_checked=len(records),
        independent_methods=['Graph reachability for dependency blocks','All-label enumeration modulo permutations','Endpoint event sweep','Resource-ID overlap and unchanged task windows'],
        interpretation='Whole relay sortie and all services it supports remain in one group because task and guarantee relations are frozen; this is an explicit fixed-task-domain interpretation',
        fixed_F13_domain_only=True,representatives=summary)
    write(q/'independent_validation.json',result)
    print('Q4_CHECK',n,counts,[(x['partition_id'],x['total_shortage_units'],x['workload_cv']) for x in summary],flush=True)
if __name__=='__main__':main()
