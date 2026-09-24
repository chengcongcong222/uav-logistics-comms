"""Exact independent K=2/3 partitions of a frozen Gamma=0 Q3 execution."""
from pathlib import Path
from collections import defaultdict
import hashlib,heapq,itertools,json,math
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'results/reset/q4';SOURCE=ROOT/'results/reset/q3/A11/solutions/A11_Q3_001';DATA=ROOT/'results/reset/geometry'
KINDS=['TUAV_A','TUAV_B','TUAV_C','TBAT_A','TBAT_B','TBAT_C','RUAV','REC'];TOL=1e-6
def read(p):return pd.read_csv(p,float_precision='round_trip')
def write(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,indent=2,ensure_ascii=False)+'\n')
def csv(p,rows):p.parent.mkdir(parents=True,exist_ok=True);pd.DataFrame(rows).to_csv(p,index=False)

def load():
    t=read(SOURCE/'transport_sorties_A11.csv');r=read(SOURCE/'relay_sorties_A11.csv');g=read(SOURCE/'communication_guarantee_A11.csv');b=read(SOURCE/'box_delivery_A11.csv')
    services={x.sortie_id:x.service_sequence.split('>') for x in t.itertuples()};edges=[]
    for sid,ss in services.items():edges.append(dict(kind='TRANSPORT_VISIT',task_id=sid,services=ss))
    for rid,frame in g.groupby('relay_sortie_id'):
        ss=sorted({s for sid in frame.transport_sortie_id for s in services[sid]})
        edges.append(dict(kind='RELAY_COMMUNICATION_DEPENDENCY',task_id=rid,services=ss))
    parent={f'S{i:03d}':f'S{i:03d}' for i in range(1,16)}
    def find(s):
        while parent[s]!=s:s=parent[s]
        return s
    for edge in edges:
        first=find(edge['services'][0])
        for s in edge['services'][1:]:parent[find(s)]=first
    merged=defaultdict(list)
    for s in sorted(parent):merged[find(s)].append(s)
    blocks=sorted(merged.values());membership={s:i for i,ss in enumerate(blocks) for s in ss}
    blockt={sid:membership[ss[0]] for sid,ss in services.items()};blockr={x['task_id']:membership[x['services'][0]] for x in edges if x['kind'].startswith('RELAY')}
    calendars=[]
    for x in t.itertuples():calendars.append(dict(kind='TUAV_'+x.uav_type,task_id=x.sortie_id,block=blockt[x.sortie_id],start_s=x.preparation_start_s,end_s=x.return_s,source_resource_id=x.uav_id))
    for x in read(SOURCE/'transport_battery_calendar_A11.csv').itertuples():
        typ=t.set_index('sortie_id').loc[x.sortie_id].uav_type
        calendars.append(dict(kind='TBAT_'+typ,task_id=x.sortie_id,block=blockt[x.sortie_id],start_s=x.takeoff_s,end_s=x.energy_ready_s,source_resource_id=x.battery_id))
    for x in r.itertuples():
        calendars.append(dict(kind='RUAV',task_id=x.relay_sortie_id,block=blockr[x.relay_sortie_id],start_s=x.preparation_start_s,end_s=x.uav_available_s,source_resource_id=x.relay_id))
        calendars.append(dict(kind='REC',task_id=x.relay_sortie_id,block=blockr[x.relay_sortie_id],start_s=x.takeoff_s,end_s=x.energy_ready_s,source_resource_id=x.energy_component_id))
    stock={f'TUAV_{typ}':int(n) for typ,n in read(DATA/'transport_uavs.csv').groupby('uav_type').size().items()}
    stock.update({f'TBAT_{x.uav_type}':int(x.battery_pool_count) for x in read(DATA/'transport_batteries.csv').itertuples()})
    stock.update(RUAV=len(read(DATA/'relay_uavs.csv')),REC=int(read(DATA/'relay_energy_components.csv').energy_pool_count.sum()))
    return t,r,g,b,blocks,edges,blockt,blockr,calendars,stock

def allocate(rows,prefix):
    busy=[];free=[];count=0;assigned=[]
    for row in sorted(rows,key=lambda x:(x['start_s'],x['end_s'],x['task_id'])):
        while busy and busy[0][0]<=row['start_s']+TOL:
            _,rid=heapq.heappop(busy);heapq.heappush(free,rid)
        if free:rid=heapq.heappop(free)
        else:count+=1;rid=count
        heapq.heappush(busy,(row['end_s'],rid));assigned.append(dict(row,resource_id=f'{prefix}-{rid:02d}'))
    witness=[];at=None
    for row in rows:
        active=[x['task_id'] for x in rows if x['start_s']<=row['start_s'] and x['end_s']>row['start_s']+TOL]
        if len(active)>len(witness):witness=active;at=row['start_s']
    assert len(witness)==count,(prefix,count,witness)
    return count,assigned,dict(time_s=at,task_ids=witness,count=count)

def partitions(n,k,prefix=(0,)):
    if len(prefix)==n:
        if max(prefix)+1==k:yield prefix
        return
    for label in range(min(k,max(prefix)+2)):
        yield from partitions(n,k,prefix+(label,))

def evaluate(labels,data):
    t,r,g,b,blocks,edges,blockt,blockr,calendars,stock=data;k=max(labels)+1;groups=[];allocated=[];totals={kind:0 for kind in KINDS}
    boxes=read(DATA/'boxes.csv').set_index('box_id');horizon=max(x['end_s'] for x in calendars)
    for group in range(k):
        ss=sorted(s for i,block in enumerate(blocks) if labels[i]==group for s in block);need={};cert={};rows=[x for x in calendars if labels[x['block']]==group]
        for kind in KINDS:
            n,assigned,c=allocate([x for x in rows if x['kind']==kind],f'G{group+1}-{kind}');need[kind]=n;cert[kind]=c;totals[kind]+=n
            allocated += [dict(x,group_id=f'G{group+1}') for x in assigned]
        boxids=list(b[b.service_id.isin(ss)].box_id)
        work=sum(x['end_s']-x['start_s'] for x in rows if x['kind'].startswith('TUAV_') or x['kind']=='RUAV')
        groups.append(dict(group_id=f'G{group+1}',services=ss,resources=need,peak_certificates=cert,workload_uav_occupied_s=work,
            box_count=len(boxids),mass_kg=float(boxes.loc[boxids].mass_kg.sum()),transport_sorties=sum(labels[i]==group for i in blockt.values()),
            relay_sorties=sum(labels[i]==group for i in blockr.values()),allocated_resource_time_s=sum(need.values())*horizon,
            occupied_resource_time_s=sum(x['end_s']-x['start_s'] for x in rows)))
    works=np.array([x['workload_uav_occupied_s'] for x in groups]);gap={kind:max(0,totals[kind]-stock[kind]) for kind in KINDS}
    result=dict(k=k,labels=list(labels),groups=groups,resources=totals,inventory=stock,shortage=gap,inventory_surplus={kind:max(0,stock[kind]-totals[kind]) for kind in KINDS},
        total_resource_units=sum(totals.values()),total_shortage_units=sum(gap.values()),inventory_feasible=not any(gap.values()),
        workload_cv=float(works.std()/works.mean()),workload_max_min_ratio=float(works.max()/works.min()),resource_horizon_s=horizon,
        workload_definition='SUM_TRANSPORT_PREP_TO_RETURN_PLUS_RELAY_PREP_TO_TURNAROUND_END',calendar=allocated)
    return result

def dominates(a,b):
    dims=[a['resources'][kind]-b['resources'][kind] for kind in KINDS]+[a['workload_cv']-b['workload_cv']]
    return all(d<=1e-12 for d in dims) and any(d< -1e-12 for d in dims)

def flatten(r):
    return dict(partition_id=r['partition_id'],k=r['k'],labels=json.dumps(r['labels']),groups=json.dumps([g['services'] for g in r['groups']]),
        total_resource_units=r['total_resource_units'],total_shortage_units=r['total_shortage_units'],inventory_feasible=r['inventory_feasible'],workload_cv=r['workload_cv'],
        **{f'required_{x}':r['resources'][x] for x in KINDS},**{f'shortage_{x}':r['shortage'][x] for x in KINDS},**{f'redundancy_{x}':r['redundancy'][x] for x in KINDS})

def export(result,data):
    t,r,g,b,blocks,edges,blockt,blockr,calendars,stock=data;d=OUT/'solutions'/result['partition_id'];d.mkdir(parents=True,exist_ok=True)
    labels=result['labels'];gt={sid:f'G{labels[i]+1}' for sid,i in blockt.items()};gr={sid:f'G{labels[i]+1}' for sid,i in blockr.items()}
    alloc={(x['kind'],x['task_id']):x['resource_id'] for x in result['calendar']}
    t=t.copy();r=r.copy();g=g.copy();b=b.copy()
    for field,kind in [('uav_id','TUAV_'),('battery_id','TBAT_')]:
        t['source_'+field]=t[field];t[field]=[alloc[kind+x.uav_type,x.sortie_id] for x in t.itertuples()]
    t['group_id']=t.sortie_id.map(gt)
    for field,kind in [('relay_id','RUAV'),('energy_component_id','REC')]:r['source_'+field]=r[field];r[field]=[alloc[kind,x.relay_sortie_id] for x in r.itertuples()]
    r['group_id']=r.relay_sortie_id.map(gr);g['source_relay_id']=g.relay_id;g.relay_id=g.relay_sortie_id.map(r.set_index('relay_sortie_id').relay_id);g['group_id']=g.transport_sortie_id.map(gt)
    assert (g.group_id==g.relay_sortie_id.map(gr)).all();b['group_id']=b.sortie_id.map(gt)
    for name,frame in [('transport_sorties',t),('relay_sorties',r),('communication_guarantee',g),('box_delivery',b)]:csv(d/f'{name}.csv',frame.to_dict('records'))
    csv(d/'resource_calendar.csv',result['calendar']);csv(d/'service_partition.csv',[dict(service_id=s,group_id=x['group_id']) for x in result['groups'] for s in x['services']])
    write(d/'configuration.json',result)

def main():
    OUT.mkdir(exist_ok=True);data=load();t,r,g,b,blocks,edges,blockt,blockr,calendars,stock=data
    baseline={kind:allocate([x for x in calendars if x['kind']==kind],'GLOBAL-'+kind)[0] for kind in KINDS}
    write(OUT/'blocks.json',dict(blocks=blocks,hyperedges=edges,global_minimum_resources=baseline,inventory=stock))
    records=[];selected=[];balanced=[]
    for k in [2,3]:
        rows=[]
        for i,labels in enumerate(partitions(len(blocks),k),1):
            result=evaluate(labels,data);result['partition_id']=f'Q4_K{k}_{i:03d}';result['redundancy']={kind:result['resources'][kind]-baseline[kind] for kind in KINDS};rows.append(result)
        frontier=[x for x in rows if not any(dominates(y,x) for y in rows)]
        best=min(rows,key=lambda x:(x['total_shortage_units'],x['total_resource_units'],x['workload_cv'],tuple(x['labels'])))
        assert best in frontier;selected.append(best['partition_id']);export(best,data)
        balance=min(frontier,key=lambda x:(x['workload_cv'],x['total_shortage_units'],x['total_resource_units'],tuple(x['labels'])))
        balanced.append(balance['partition_id']);export(balance,data)
        csv(OUT/f'all_partitions_K{k}.csv',[flatten(x) for x in rows]);csv(OUT/f'pareto_partitions_K{k}.csv',[flatten(x) for x in frontier]);records+=rows
        print('Q4',k,'enumerated',len(rows),'frontier',len(frontier),'selected',flatten(best),flush=True)
    write(OUT/'all_partitions.json',records)
    config=dict(source_solution='A11_Q3_001',Gamma_C_db=0,k=[2,3],selected=selected,balanced_alternatives=balanced,
        inherited_structure='TRANSPORT_VISIT_AND_WHOLE_RELAY_SORTIE_COMMUNICATION_DEPENDENCY_BLOCKS',
        task_times_routes_service_relations_frozen=True,resource_ids='RECOLORED_WITHIN_GROUP_ONLY; SOURCE_IDS_RETAINED_FOR_PROVENANCE',
        minimum_resource_method='INTERVAL_GRAPH_PEAK_CLIQUE_WITH_MATCHING_COLORING',time_tolerance_s=TOL,
        pareto_dimensions=KINDS+['workload_cv'],selection='LEX_MIN_TOTAL_SHORTAGE_UNITS_THEN_TOTAL_RESOURCE_UNITS_THEN_WORKLOAD_CV_THEN_LABELS',
        selection_counts_are_not_monetary_costs=True,randomized=False,source_robustness='STANDARD_GAMMA_ZERO_ONLY',
        E8B_is_not_a_gate=True,resource_shortages_allowed_as_reported_Q4_outputs=True)
    write(OUT/'config.json',config)
    sources=list(SOURCE.glob('*'));sources+=[DATA/x for x in ['transport_uavs.csv','transport_batteries.csv','relay_uavs.csv','relay_energy_components.csv','boxes.csv']]
    sources+=list((ROOT/'data/raw').glob('*.docx'))
    write(OUT/'input_manifest.json',dict(source_commit='G2_RESET_WORKTREE_BOUND_BY_FILE_HASHES',hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources if p.is_file()}))

if __name__=='__main__':main()
