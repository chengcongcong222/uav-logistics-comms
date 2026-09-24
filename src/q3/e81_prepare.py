"""One critical-window diagnosis and one bounded candidate-expansion batch."""
from pathlib import Path
from src.q3.e8_search import *
from src.q3.e8_seed_variants import partition
E81=Q3/'e81'

def cover(tasks,edges):
    # Exact set cover by dynamic programming over active-demand masks.
    masks={}
    for s in sorted(set().union(*(edges[a] for a in tasks))):
        mask=sum(1<<i for i,a in enumerate(tasks) if s in edges[a])
        if mask:masks.setdefault(mask,s)
    best={0:[]};target=(1<<len(tasks))-1
    for mask,site in masks.items():
        for old,chosen in list(best.items()):
            new=old|mask
            if new not in best or len(chosen)+1<len(best[new]):best[new]=chosen+[site]
    return best.get(target)

def prepare():
    E81.mkdir(exist_ok=True)
    assert not (E81/'candidate_expansion.json').exists(),'The one authorized diagnosis/expansion batch is already complete'
    e=load_engine(6)
    baseline=json.loads((E7/'solutions/Q3E7_001/witness.json').read_text());shifts=baseline['shifts']
    original=e.atoms.copy();pool=list(read(gamma_dir(6)/'candidate_sites.csv').site_id)
    edges={a:set(e.edges['P01'][a]) for a in e.atoms.index}
    events=sorted({float(t.service_start_s+shifts[t.transport_sortie_id]) for t in original.itertuples()}|{float(t.service_end_s+shifts[t.transport_sortie_id]) for t in original.itertuples()})
    obstruction=None;scans=[]
    for a,b in zip(events[:-1],events[1:]):
        active=[t.atomic_task_id for t in original.itertuples() if t.service_start_s+shifts[t.transport_sortie_id]<=a+1e-7 and t.service_end_s+shifts[t.transport_sortie_id]>=b-1e-7]
        if not active:continue
        selected=cover(active,edges);scans.append(dict(start_s=a,end_s=b,active=active,minimum_full_atom_cover=len(selected) if selected is not None else None))
        if selected and len(selected)>2:obstruction=(a,b,active,selected);break
    assert obstruction,'No fixed-reference candidate-cover overload detected'
    a,b,active,selected=obstruction;mid=(a+b)/2;instant={}
    for aid in active:
        t=original.loc[aid];tr=e.trajectories['P01',t.transport_sortie_id]
        instant[aid]={s for s in pool if e.backhaul(e.sites[s])>=0 and e.access(tr,e.sites[s],mid-shifts[t.transport_sortie_id])[0]>=0}
    instant_cover=cover(active,instant)
    timing=Timing(e,'P01',[]);critical=[]
    # Close the early window over hard-deadline flights whose latest landing is
    # before 5000 s. This is a declared diagnostic window, not a new deadline.
    for sid,r in timing.transport.iterrows():
        cap=timing.bounds[timing.idx[sid]][1]
        if r.return_s+cap<5000:critical.append(sid)
    task_rows=[];occupancies=[];intersections=[]
    for aid in active:
        t=original.loc[aid];d=shifts[t.transport_sortie_id];lo,hi=timing.bounds[timing.idx[t.transport_sortie_id]]
        task_rows.append(dict(atomic_task_id=aid,transport_sortie_id=t.transport_sortie_id,service_start_s=t.service_start_s+d,service_end_s=t.service_end_s+d,
            shift_lower_s=lo,shift_upper_s=hi,whole_atom_candidates=len(edges[aid]),instantaneous_candidates=len(instant[aid])))
        for site in sorted(edges[aid]):
            en=e.energy(e.sites[site],0)
            occupancies.append(dict(atomic_task_id=aid,site_id=site,preparation_start_s=t.service_start_s+d-210-en['outbound_time_s'],
                service_start_s=t.service_start_s+d,service_end_s=t.service_end_s+d,uav_available_s=t.service_end_s+d+en['return_time_s']+300))
    for x,y in itertools.combinations(active,2):intersections.append(dict(tasks=[x,y],whole_atom_common=sorted(edges[x]&edges[y]),instant_common=sorted(instant[x]&instant[y])))
    diagnosis=dict(reference_solution='Q3E7_001',Gamma_C_db=6,earliest_reference_full_atom_overload_window_s=[a,b],
        active_robust_tasks=task_rows,hard_deadline_transport_sorties=critical,candidate_pool_sites=len(pool),
        minimum_simultaneous_relays_under_full_interval_candidate_pool=len(selected),set_cover_witness=selected,
        snapshot_time_s=mid,minimum_relays_at_physical_snapshot=len(instant_cover) if instant_cover else None,
        instantaneous_site_cover=instant_cover,candidate_common_site_intersections=intersections,
        scope='FIXED_E7_REFERENCE_TIMING; FULL_POOL_SET_COVER_EXACT; NOT_A_LOWER_BOUND_FOR_FREE_L1_TIMING',
        critical_closure_rule='HARD_DEADLINE_FLIGHTS_WITH_LATEST_RETURN_BEFORE_5000S',scanned_event_windows=scans,
        energy_component_bottleneck_excluded=False,physical_infeasibility_proven=False)
    write_json(E81/'critical_window_diagnosis.json',diagnosis);write_csv(E81/'required_relay_occupation_intervals.csv',occupancies)
    # One subdivision and one candidate batch, preserving the guarded union.
    tasks=[]
    for t in original.to_dict('records'):
        count=math.ceil(t['service_duration_s']/60) if t['transport_sortie_id'] in critical else 1
        ends=np.linspace(t['service_start_s'],t['service_end_s'],count+1)
        for j,(x,y) in enumerate(zip(ends[:-1],ends[1:])):
            tasks.append(dict(t,atomic_task_id=t['atomic_task_id']+f'_R{j:02d}',service_start_s=float(x),service_end_s=float(y),service_duration_s=float(y-x)))
    e.atoms=pd.DataFrame(tasks).set_index('atomic_task_id',drop=False);e.edges={'P01':{t['atomic_task_id']:{} for t in tasks}};e.edge_cache.clear()
    for site in pool:e.add_edges(site)
    active_new=[t.atomic_task_id for t in e.atoms.itertuples() if t.service_start_s+shifts[t.transport_sortie_id]<b and t.service_end_s+shifts[t.transport_sortie_id]>a]
    targets=[]
    for x,y in itertools.combinations(active_new,2):
        if e.atoms.loc[x].transport_sortie_id!=e.atoms.loc[y].transport_sortie_id and not e.common([x,y]):targets.append([x,y])
    # Single fixed batch, no adaptive retry or whole-DEM search.
    for target in targets[:8]:e.search_common(target,max_checks=250,wanted=2,rank='origin')
    pairs=[r for ss in e.edges['P01'].values() for r in ss.values()];used=sorted({r['site_id'] for r in pairs});sites=[]
    for sid in used:
        s={k:v for k,v in e.sites[sid].items() if k!='static_energy'}
        s['backhaul_robust_slack_db']=s['backhaul_margin_db'];s['backhaul_margin_db']+=6;sites.append(s)
    write_csv(E81/'robust_tasks.csv',tasks);write_csv(E81/'candidate_pairs.csv',pairs);write_csv(E81/'candidate_sites.csv',sites)
    outside=[]
    for start in [9,17,25]:
        ids=[t.atomic_task_id for t in e.atoms.itertuples() if t.transport_sortie_id not in critical and start<=int(t.transport_sortie_id[1:])<start+8]
        if ids:outside+=partition(e,ids,'unit')
    write_json(E81/'outside_window_groups.json',outside)
    write_json(E81/'candidate_expansion.json',dict(batches=1,max_target_groups=8,max_checks_per_group=250,
        targeted_pairs=targets[:8],searches=e.search_log,tasks=len(tasks),sites=len(sites),edges=len(pairs),
        unresolved=[a for a,ss in e.edges['P01'].items() if not ss],critical_transport_ids=critical,
        max_critical_atom_duration_s=60,outside_grouping_frozen=True))
    write_json(E81/'config.json',dict(Gamma_C_db=6,diagnosis_rounds=1,expansion_batches=1,feasibility_searches=1,
        search_time_limit_s=180,objective='FEASIBILITY_ONLY',critical_transport_ids=critical,
        relay_count=2,energy_components=6,sortie_cap='ONE_NONEMPTY_SORTIE_PER_CRITICAL_ATOM_PLUS_FIXED_OUTSIDE_GROUPS; NO_2_OR_3_CAP',
        transport_structure_frozen=True,transport_timing='E7_L1_FREE',stop_after_this_search=True,next_stage='Q4_REGARDLESS_OF_GAMMA6_RESULT'))
    print('E81_PREPARED',diagnosis['earliest_reference_full_atom_overload_window_s'],len(selected),len(tasks),len(sites),flush=True)

def engine():
    e=load_engine(6);e.atoms=read(E81/'robust_tasks.csv').set_index('atomic_task_id',drop=False);e.edges={'P01':{a:{} for a in e.atoms.index}};e.edge_cache.clear()
    for r in read(E81/'candidate_sites.csv').to_dict('records'):e.add_site(r['x_m'],r['y_m'],r['agl_m'])
    for r in read(E81/'candidate_pairs.csv').to_dict('records'):e.edges['P01'][r['atomic_task_id']][r['site_id']]=r
    return e

if __name__=='__main__':prepare()
