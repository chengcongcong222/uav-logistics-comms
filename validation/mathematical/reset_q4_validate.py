"""Independent Q4 validation: graph traversal, event sweeps and enumeration.

No partition optimizer or interval-coloring implementation is imported.
"""
from pathlib import Path
from collections import defaultdict
import hashlib,itertools,json,math
import pandas as pd
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'results/reset/q4';SOURCE=ROOT/'results/reset/q3/A11/solutions/A11_Q3_001';DATA=ROOT/'results/reset/geometry'
KINDS=['TUAV_A','TUAV_B','TUAV_C','TBAT_A','TBAT_B','TBAT_C','RUAV','REC'];TOL=1e-6
def read(p):return pd.read_csv(p,float_precision='round_trip')
def require(ok,message):
    if not ok:raise ValueError(message)
def peak(intervals):
    events=sorted([(a,1) for a,b in intervals]+[(b-TOL,-1) for a,b in intervals]);n=best=0
    for t,d in events:n+=d;best=max(best,n)
    return best
def canonical(labels):
    seen={}
    return tuple(seen.setdefault(x,len(seen)) for x in labels)
def close(a,b,label,tol=1e-7):require(abs(float(a)-float(b))<=tol,label)

def validate():
    config=json.loads((OUT/'config.json').read_text());require(config['Gamma_C_db']==0 and config['source_solution']=='A11_Q3_001','Wrong Q4 authority')
    manifest=json.loads((OUT/'input_manifest.json').read_text())
    for f,h in manifest['hashes'].items():require(hashlib.sha256((ROOT/f).read_bytes()).hexdigest()==h,'Changed source '+f)
    sourceaudit=json.loads((SOURCE/'validation_0.5.json').read_text());require(sourceaudit['status']=='G2_Q3_INDEPENDENTLY_VALIDATED','Source Q3 not validated')
    for f,h in sourceaudit['artifact_sha256'].items():require(hashlib.sha256((ROOT/f).read_bytes()).hexdigest()==h,'Stale source audit '+f)
    t=read(SOURCE/'transport_sorties_A11.csv').set_index('sortie_id');r=read(SOURCE/'relay_sorties_A11.csv').set_index('relay_sortie_id');g=read(SOURCE/'communication_guarantee_A11.csv');b=read(SOURCE/'box_delivery_A11.csv')
    battery=read(SOURCE/'transport_battery_calendar_A11.csv').set_index('sortie_id');stock={}
    for typ,n in read(DATA/'transport_uavs.csv').groupby('uav_type').size().items():stock['TUAV_'+typ]=int(n)
    for x in read(DATA/'transport_batteries.csv').itertuples():stock['TBAT_'+x.uav_type]=int(x.battery_pool_count)
    stock.update(RUAV=len(read(DATA/'relay_uavs.csv')),REC=int(read(DATA/'relay_energy_components.csv').energy_pool_count.sum()))
    service_sets={sid:set(x.service_sequence.split('>')) for sid,x in t.iterrows()};relaysets={rid:set().union(*(service_sets[sid] for sid in part.transport_sortie_id)) for rid,part in g.groupby('relay_sortie_id')}
    graph={f'S{i:03d}':set() for i in range(1,16)}
    for edge in list(service_sets.values())+list(relaysets.values()):
        for a in edge:graph[a].update(edge-{a})
    components=[];remaining=set(graph)
    while remaining:
        stack=[min(remaining)];component=set()
        while stack:
            s=stack.pop()
            if s in component:continue
            component.add(s);stack+=list(graph[s]-component)
        remaining-=component;components.append(sorted(component))
    components.sort();blocks=json.loads((OUT/'blocks.json').read_text());require(components==blocks['blocks'],'Dependency components differ')
    intervals={}
    for sid,x in t.iterrows():
        intervals['TUAV_'+x.uav_type,sid]=(x.preparation_start_s,x.return_s,service_sets[sid])
        intervals['TBAT_'+x.uav_type,sid]=(x.takeoff_s,battery.loc[sid].energy_ready_s,service_sets[sid])
    for rid,x in r.iterrows():
        intervals['RUAV',rid]=(x.preparation_start_s,x.uav_available_s,relaysets[rid])
        intervals['REC',rid]=(x.takeoff_s,x.energy_ready_s,relaysets[rid])
    global_min={kind:peak([(a,z) for (kk,s),(a,z,ss) in intervals.items() if kk==kind]) for kind in KINDS}
    require(global_min==blocks['global_minimum_resources'],'Global pool minima');require(stock==blocks['inventory'],'Inventory')
    rows=json.loads((OUT/'all_partitions.json').read_text());byid={q['partition_id']:q for q in rows};require(len(byid)==len(rows),'Duplicate partition IDs')
    counts={};front_counts={}
    for k in [2,3]:
        expected={canonical(x) for x in itertools.product(range(k),repeat=len(components)) if len(set(x))==k}
        actual=[q for q in rows if q['k']==k];require({tuple(q['labels']) for q in actual}==expected,'Incomplete or extra partition enumeration');require(len(actual)==len(expected),'Duplicate partitions');counts[k]=len(actual)
        for q in actual:
            service_group={s:f'G{q["labels"][i]+1}' for i,comp in enumerate(components) for s in comp};totals={kind:0 for kind in KINDS};work=[]
            for group in q['groups']:
                gid=group['group_id'];ss={s for s,label in service_group.items() if label==gid};require(ss==set(group['services']) and len(ss)>0,'Group service set')
                totalwork=0
                for kind in KINDS:
                    selected=[(sid,a,z) for (kk,sid),(a,z,vs) in intervals.items() if kk==kind and vs<=ss]
                    n=peak([(a,z) for sid,a,z in selected]);require(n==group['resources'][kind],'Nonminimal resource allocation');totals[kind]+=n
                    cert=group['peak_certificates'][kind];require(cert['count']==n and len(cert['task_ids'])==n,'Wrong peak witness cardinality')
                    if n:
                        at=cert['time_s'];active={sid for sid,a,z in selected if a<=at and z>at+TOL};require(set(cert['task_ids'])==active,'Invalid concurrency lower bound')
                    if kind.startswith('TUAV_') or kind=='RUAV':totalwork+=sum(z-a for sid,a,z in selected)
                close(totalwork,group['workload_uav_occupied_s'],'Workload');work.append(totalwork)
            require(totals==q['resources'],'Resource totals');require(q['shortage']=={kind:max(0,totals[kind]-stock[kind]) for kind in KINDS},'Shortage vector')
            require(q['redundancy']=={kind:totals[kind]-global_min[kind] for kind in KINDS},'Partition redundancy')
            mean=sum(work)/k;cv=math.sqrt(sum((w-mean)**2 for w in work)/k)/mean;close(cv,q['workload_cv'],'Workload CV',1e-12)
            require(sum(q['shortage'].values())==q['total_shortage_units'] and sum(totals.values())==q['total_resource_units'],'Summary counts')
        def dominates(a,b):
            av=[a['resources'][kind] for kind in KINDS]+[a['workload_cv']];bv=[b['resources'][kind] for kind in KINDS]+[b['workload_cv']]
            return all(x<=y+1e-12 for x,y in zip(av,bv)) and any(x<y-1e-12 for x,y in zip(av,bv))
        frontier={q['partition_id'] for q in actual if not any(dominates(p,q) for p in actual)}
        require(frontier==set(read(OUT/f'pareto_partitions_K{k}.csv').partition_id),'Incorrect Pareto subset');front_counts[k]=len(frontier)
        best=min(actual,key=lambda q:(q['total_shortage_units'],q['total_resource_units'],q['workload_cv'],tuple(q['labels'])))
        require(best['partition_id']==config['selected'][k-2],'Wrong resource-priority representative')
        balanced=min((byid[s] for s in frontier),key=lambda q:(q['workload_cv'],q['total_shortage_units'],q['total_resource_units'],tuple(q['labels'])))
        require(balanced['partition_id']==config['balanced_alternatives'][k-2],'Wrong balance alternative')
    # Verify the template exports independently of the report generator.
    import openpyxl
    for name,ids in [('Q4_分区配置_缺口优先.xlsx',config['selected']),('Q4_分区配置_均衡优先.xlsx',config['balanced_alternatives'])]:
        workbook=OUT/name
        require(workbook.exists(),'Missing Q4 template workbook')
        if workbook.exists():
            ws=openpyxl.load_workbook(workbook,read_only=True,data_only=True)['Q4_分区配置']
            expected=[]
            for sid in ids:
                for group in byid[sid]['groups']:
                    expected.append(tuple([byid[sid]['k'],group['group_id'],','.join(group['services'])]+[group['resources'][kind] for kind in KINDS]))
            require(list(ws.iter_rows(min_row=2,max_row=1+len(expected),max_col=11,values_only=True))==expected,'Template export differs from validated configurations')
    packages=[]
    for sid in sorted(set(config['selected']+config['balanced_alternatives'])):
        d=OUT/'solutions'/sid;q=byid[sid];sp=read(d/'service_partition.csv');require(len(sp)==15 and sp.service_id.is_unique,'15 services once')
        sg=sp.set_index('service_id').group_id.to_dict();cal=read(d/'resource_calendar.csv');require(len(cal)==len(intervals),'Calendar complete')
        require(not cal.duplicated(['kind','task_id']).any(),'Duplicate task resource occupancy')
        assignments={}
        for x in cal.itertuples():
            a,z,services=intervals[x.kind,x.task_id];close(x.start_s,a,'Frozen resource start');close(x.end_s,z,'Frozen resource end')
            require({sg[s] for s in services}=={x.group_id},'Cross-group mission dependency')
            require(x.resource_id.startswith(x.group_id+'-'+x.kind+'-'),'Resource not group/type specific');assignments[x.kind,x.task_id]=x.resource_id
        for rid,part in cal.groupby('resource_id'):
            require(part.group_id.nunique()==part.kind.nunique()==1,'Resource shared across groups/types')
            ordered=part.sort_values('start_s');end=0
            for x in ordered.itertuples():require(x.start_s>=end-TOL,'Resource overlap');end=x.end_s
        for group in q['groups']:
            for kind,n in group['resources'].items():require(cal[(cal.group_id==group['group_id'])&(cal.kind==kind)].resource_id.nunique()==n,'Calendar does not attain minimum')
        for stem,base,index,change in [('transport_sorties',t,'sortie_id',['uav_id','battery_id']),('relay_sorties',r,'relay_sortie_id',['relay_id','energy_component_id']),('communication_guarantee',g.set_index('atomic_task_id'),'atomic_task_id',['relay_id']),('box_delivery',b.set_index('box_id'),'box_id',[])]:
            new=read(d/f'{stem}.csv').set_index(index);require(set(new.index)==set(base.index),'Changed source identities')
            for col in base.columns:
                if col in change:require((new['source_'+col].astype(str)==base[col].astype(str)).all(),'Source resource provenance');continue
                for key,v in base[col].items():
                    value=new.loc[key,col]
                    if pd.isna(v):require(pd.isna(value),'Changed missing source field')
                    elif isinstance(v,(int,float)) and not isinstance(v,bool):close(v,value,'Frozen task value '+col,1e-8)
                    else:require(v==value,'Frozen task field '+col)
            for key,x in new.iterrows():
                if stem=='transport_sorties':
                    require(x.uav_id==assignments['TUAV_'+x.uav_type,key] and x.battery_id==assignments['TBAT_'+x.uav_type,key],'Transport ID/calendar mismatch')
                elif stem=='relay_sorties':require(x.relay_id==assignments['RUAV',key] and x.energy_component_id==assignments['REC',key],'Relay ID/calendar mismatch')
                elif stem=='communication_guarantee':require(x.relay_id==assignments['RUAV',x.relay_sortie_id] and sg[next(iter(service_sets[x.transport_sortie_id]))]==x.group_id,'Guarantee group/provider')
        result=dict(partition_id=sid,status='Q4_PARTITION_INDEPENDENTLY_VALIDATED',minimum_resources_certified=True,frozen_tasks_and_communications_preserved=True,
            inventory_feasible=q['inventory_feasible'],shortage=q['shortage'],requires_additional_inventory=not q['inventory_feasible'])
        (d/'validation.json').write_text(json.dumps(result,indent=2)+'\n');packages.append(result)
    result=dict(gate='Q4_INDEPENDENT_PARTITIONS_READY',source_solution='A11_Q3_001',Gamma_C_db=0,unsplittable_blocks=len(components),enumerated_partitions=counts,
        exact_pareto_partitions=front_counts,validated_packages=packages,all_partition_resource_minima_certified=True,
        scope='EXACT_FOR_FIXED_G2_A11_Q3_001_TASKS_AND_WHOLE_RELAY_DEPENDENCY_PARTITIONS',
        inventory_infeasibility_is_a_reported_Q4_outcome=True,E8B_is_not_a_gate=True)
    files=[p for p in OUT.rglob('*') if p.is_file() and p!=OUT/'validation.json' and p.suffix!='.log']
    files += [ROOT/'src/reset/q4.py',ROOT/'validation/mathematical/test_reset_regressions.py',Path(__file__)]
    for optional in ['src/reset/q4_report.py','docs/model/Q4_PARTITION_SEMANTICS.md','results/reset/q4/Q4_REPORT.md','results/reset/q4/Q4_GPT_SYNC.md']:
        p=ROOT/optional
        if p.exists():files.append(p)
    result['artifact_sha256']={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(set(files))}
    (OUT/'validation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='artifact_sha256'},indent=2))

if __name__=='__main__':validate()
