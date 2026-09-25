"""Necessary relay-occupation cuts + free typed transport CP master.

Cuts concern unsplit guarded atomic tasks and the 118 frozen sites. They never
follow from a solver timeout. A limited pricing failure triggers a labeled
heuristic timing exclusion only in a separate search domain, not a proof cut.
"""
import argparse,itertools,math,time,warnings
import numpy as np
from ortools.sat.python import cp_model
from src.bench_p1_4.common import *
from src.bench_p1_4.fixed import run

SCALE=10
def floor(x):return math.floor(x*SCALE+1e-8)
def ceil(x):return math.ceil(x*SCALE-1e-8)

def domain(e):
    core=adapter.core.Timing(e,e.pid,[],late_budget=1e-4)
    stat={s:e.energy(e.sites[s],0) for s in e.sites};task={}
    for a,t in e.atoms.iterrows():
        sites=sorted(e.common([a]));minimum_lead=min(e.pr['prep_time_s']+e.pr['setup_time_s']+stat[s]['outbound_time_s'] for s in sites)
        minimum_tail=min(stat[s]['return_time_s']+e.pr['turnaround_time_s'] for s in sites)
        prep=float(core.transport.loc[t.transport_sortie_id].preparation_start_s)
        task[a]=dict(sortie=t.transport_sortie_id,sites=sites,start_offset=float(t.service_start_s)-prep,end_offset=float(t.service_end_s)-prep,
            mandatory_start_offset=float(t.service_start_s)-prep-minimum_lead,mandatory_end_offset=float(t.service_end_s)-prep+minimum_tail,
            min_lead=minimum_lead,min_tail=minimum_tail,min_return=minimum_tail-e.pr['turnaround_time_s'])
    return core,task

def coverable(ids,tasks):
    universe=set(ids);site_sets={s:{a for a in ids if s in tasks[a]['sites']} for s in set(s for a in ids for s in tasks[a]['sites'])}
    sets=list(set(frozenset(v) for v in site_sets.values()))
    return any(universe<=(a|b) for a in sets for b in sets)

def conflicts(core,tasks,shifts):
    starts={s:float(core.transport.loc[s].preparation_start_s)+shifts[s] for s in core.ids}
    intervals={a:(starts[t['sortie']]+t['mandatory_start_offset'],starts[t['sortie']]+t['mandatory_end_offset']) for a,t in tasks.items()}
    proofs={}
    for at in sorted(set(v[0] for v in intervals.values())):
        active=[a for a,(l,r) in intervals.items() if l<=at+1e-7 and r>at+1e-7]
        if not active or coverable(active,tasks):continue
        reduced=active[:]
        for a in active:
            sub=[b for b in reduced if b!=a]
            if sub and not coverable(sub,tasks):reduced=sub
        key=tuple(sorted(reduced))
        proofs[key]=dict(tasks=list(key),mandatory_overlap=[max(intervals[a][0] for a in key),min(intervals[a][1] for a in key)],
            all_site_two_cover_impossible=True,scope='118_SITES_UNSPLIT_ATOMIC_TASK_SINGLE_SORTIE_SERVICE',
            proof='Each task forces its serving UAV to occupy its mandatory interval. Two UAVs can serve at most two sites; exhaustive two-site union cannot cover these tasks.')
    return list(proofs.values())

def transport_master(e,core,tasks,cuts,path,hint,limit=30,tabus=None,site_relaxation=False,three_pair_master=False):
    path.mkdir(parents=True,exist_ok=False);m=cp_model.CpModel();x={};bounds={};origin={s:float(core.transport.loc[s].preparation_start_s) for s in core.ids}
    for s in core.ids:
        i=core.idx[s];rows=core.delivery[core.delivery.sortie_id==s];latest=origin[s]+core.bounds[i][1]
        for r in rows.itertuples():
            j=list(core.delivery.box_id).index(r.box_id)
            latest=min(latest,origin[s]+core.deadlines[j]-float(r.delivery_time_s))
        bounds[s]=(0,floor(latest));x[s]=m.NewIntVar(*bounds[s],'start_'+s)
    T=m.NewIntVar(0,400000,'joint_completion_lower_envelope')
    m.Add(T<=floor(CAP))
    for s in core.ids:m.Add(T>=x[s]+ceil(float(core.transport.loc[s].return_s)-origin[s]))
    for kind,typ,specs,allowed in core.resource_specs:
        ints=[]
        for i,a,b in specs:
            s=core.ids[i];offset=floor(a-origin[s]);duration=ceil(b-origin[s])-offset
            ints.append(m.NewFixedSizeIntervalVar(x[s]+offset,duration,kind+'_'+s))
        m.AddCumulative(ints,[1]*len(ints),len(allowed))
    for a,t in tasks.items():
        # One serving flight must reach a suitable frozen site before the atom.
        m.Add(x[t['sortie']]>=ceil(t['min_lead']-t['start_offset']))
        m.Add(T>=x[t['sortie']]+ceil(t['end_offset']+t['min_return']))
    relay_vars={};sites=sorted(e.sites)
    if site_relaxation:
        stat={s:e.energy(e.sites[s],0) for s in sites}
        lead=[ceil(e.pr['prep_time_s']+e.pr['setup_time_s']+stat[s]['outbound_time_s']) for s in sites]
        tail=[ceil(stat[s]['return_time_s']+e.pr['turnaround_time_s']) for s in sites]
        back=[ceil(stat[s]['return_time_s']) for s in sites]
        for a,t in tasks.items():
            site=m.NewIntVarFromDomain(cp_model.Domain.FromValues([sites.index(s) for s in t['sites']]),a+'_site')
            uav=m.NewBoolVar(a+'_uav');l=m.NewIntVar(min(lead),max(lead),a+'_lead');r=m.NewIntVar(min(tail),max(tail),a+'_tail');b=m.NewIntVar(min(back),max(back),a+'_back')
            m.AddElement(site,lead,l);m.AddElement(site,tail,r);m.AddElement(site,back,b)
            prep=x[t['sortie']]+floor(t['start_offset'])-l;end=x[t['sortie']]+ceil(t['end_offset'])+r
            m.Add(prep>=0);m.Add(T>=x[t['sortie']]+ceil(t['end_offset'])+b)
            relay_vars[a]=(site,uav,prep,end)
        for a,b in itertools.combinations(tasks,2):
            sa,ua,pa,ea=relay_vars[a];sb,ub,pb,eb=relay_vars[b]
            same_uav=m.NewBoolVar(a+b+'_same_uav');same_site=m.NewBoolVar(a+b+'_same_site');order=m.NewBoolVar(a+b+'_order')
            m.Add(ua==ub).OnlyEnforceIf(same_uav);m.Add(ua!=ub).OnlyEnforceIf(same_uav.Not())
            m.Add(sa==sb).OnlyEnforceIf(same_site);m.Add(sa!=sb).OnlyEnforceIf(same_site.Not())
            m.Add(ea<=pb).OnlyEnforceIf([same_uav,same_site.Not(),order])
            m.Add(eb<=pa).OnlyEnforceIf([same_uav,same_site.Not(),order.Not()])
        m.Add(relay_vars[next(iter(tasks))][1]==0)
        # At most three flights implies at most three distinct (UAV, site)
        # combinations. This is necessary, not sufficient for a flight count.
        active_sites=[]
        for ri in [0,1]:
            for sj,sid in enumerate(sites):
                eligible=[a for a,t in tasks.items() if sid in t['sites']]
                if not eligible:continue
                used=m.NewBoolVar(f'used_R{ri}_site{sj}');active_sites.append(used)
                for a in eligible:
                    sv,uv,_,_=relay_vars[a];match=m.NewBoolVar(f'{a}_at_{sj}')
                    m.Add(sv==sj).OnlyEnforceIf(match);m.Add(sv!=sj).OnlyEnforceIf(match.Not())
                    m.Add(used==1).OnlyEnforceIf([match,uv if ri else uv.Not()])
        if three_pair_master:m.Add(sum(active_sites)<=MAX_RELAY)
    for number,cut in enumerate(cuts):
        choices=[]
        for a,b in itertools.permutations(cut['tasks'],2):
            ta,tb=tasks[a],tasks[b];z=m.NewBoolVar(f'cut_{number}_{a}_{b}');choices.append(z)
            m.Add(x[ta['sortie']]-x[tb['sortie']]<=floor(tb['mandatory_start_offset']-ta['mandatory_end_offset'])).OnlyEnforceIf(z)
        m.AddBoolOr(choices)
    for j,tabu in enumerate(tabus or []):
        # Exclude this 30-second timing box as search diversification only.
        choices=[]
        for s in tabu['sorties']:
            for side in [-1,1]:
                z=m.NewBoolVar(f'heuristic_tabu_{j}_{s}_{side}');choices.append(z)
                target=round(tabu['starts'][s]*SCALE)
                if side<0:m.Add(x[s]<=target-300).OnlyEnforceIf(z)
                else:m.Add(x[s]>=target+300).OnlyEnforceIf(z)
        m.AddBoolOr(choices)
    for s in core.ids:m.AddHint(x[s],min(bounds[s][1],max(0,round((origin[s]+hint[s])*SCALE))))
    m.Minimize(T);m.ExportToFile(str(path/'model.pbtxt'))
    solver=cp_model.CpSolver();solver.parameters.max_time_in_seconds=limit;solver.parameters.num_search_workers=4;solver.parameters.random_seed=SEED
    cpu=time.process_time();wall=time.monotonic();status=solver.Solve(m);ok=status in [cp_model.OPTIMAL,cp_model.FEASIBLE]
    shifts={s:solver.Value(x[s])/SCALE-origin[s] for s in core.ids} if ok else None
    obj=solver.ObjectiveValue()/SCALE if ok else None;lb=solver.BestObjectiveBound()/SCALE
    result=dict(status=solver.StatusName(status),incumbent=obj,dual_bound=lb,gap=(obj-lb)/max(1,abs(obj)) if ok else None,
        cpu_s=time.process_time()-cpu,wall_s=time.monotonic()-wall,nodes=solver.NumBranches(),conflicts=solver.NumConflicts(),iterations=None,
        valid_necessary_cuts=len(cuts),heuristic_timing_boxes_excluded=len(tabus or []),shifts=shifts,
        scope='Conservative 0.1s transport grid; joint-completion necessary envelope plus unsplit-atom relay cuts; no full relay schedule',
        full_continuous_Q3_bound=False,seed=SEED,workers=4,response_stats=solver.ResponseStats())
    result['site_assignment_relaxation']=site_relaxation
    result['necessary_three_UAV_site_pair_cap']=three_pair_master
    if site_relaxation:
        result['site_assignment_scope']='Exact site and 2-UAV atom assignment in conservative grid; same-site atoms may share an unlimited-energy flight. Energy and component calendars relaxed, pricing validates them.'
        if ok:
            from collections import defaultdict
            groups=defaultdict(list)
            for a,(site,uav,_,_) in relay_vars.items():groups[(solver.Value(uav),sites[solver.Value(site)])].append(a)
            result['relay_guidance']=[dict(relay_index=k[0],site_id=k[1],task_ids=v) for k,v in groups.items()]
    if ok and lb>obj+1e-7:result['bound_status']='BOUND_NOT_VALID';result['dual_bound']=None
    write(path/'result.json',result);return result

def main():
    ap=argparse.ArgumentParser();ap.add_argument('pid');ap.add_argument('--iterations',type=int,default=5);ap.add_argument('--site-relaxation',action='store_true');ap.add_argument('--three-pair-master',action='store_true');args=ap.parse_args()
    warnings.filterwarnings('ignore',message='Unrecognized options detected');install_input_guard();e=engine(args.pid);core,tasks=domain(e)
    stage=('C2_SITE' if args.site_relaxation else 'C2')+('_3PAIR' if args.three_pair_master else '')+f'_B{int(CAP)}'
    root=e.root/stage;root.mkdir(exist_ok=False);write(root/'task_domain.json',tasks)
    shifts={s:0. for s in core.ids};cuts=conflicts(core,tasks,shifts);write(root/'fixed_time_conflicts.json',cuts)
    log=[];tabus=[];witnesses=[]
    for it in range(args.iterations):
        label=f'{stage}_RELAY_{it:02d}';mr=transport_master(e,core,tasks,cuts,root/f'master_{it:02d}',shifts,limit=60 if args.site_relaxation else 30,tabus=tabus,site_relaxation=args.site_relaxation,three_pair_master=args.three_pair_master)
        if not mr['shifts']:log.append(dict(iteration=it,master=mr,termination='NO_MASTER_INCUMBENT'));break
        shifts=mr['shifts'];new=conflicts(core,tasks,shifts)
        keys={tuple(c['tasks']) for c in cuts};new=[c for c in new if tuple(c['tasks']) not in keys]
        row=dict(iteration=it,master=mr,new_valid_cuts=new)
        if new:cuts+=new;row['action']='VALID_OCCUPATION_CUTS_ONLY'
        else:
            result,gen=run(e,shifts,label,rounds=2,limit=20,guidance=mr.get('relay_guidance'))
            row['relay_result']=str((e.root/label/'result.json').relative_to(ROOT))
            if result['witnesses']:
                witnesses+=result['witnesses'];row['action']='INDEPENDENTLY_VALIDATED';log.append(row);write(root/'log.json',log);break
            uncovered=result['iterations'][-1].get('uncovered_tasks',list(tasks))
            if not uncovered:uncovered=list(tasks)
            sorties=sorted(set(tasks[a]['sortie'] for a in uncovered))
            tabus.append(dict(sorties=sorties,starts={s:float(core.transport.loc[s].preparation_start_s)+shifts[s] for s in sorties},
                proof_status='HEURISTIC_SEARCH_EXCLUSION_NOT_INFEASIBILITY_CUT',reason='Diversify failed bounded pricing; retains original feasible-domain uncertainty'))
            row['action']='HEURISTIC_TIMING_DIVERSIFICATION';row['tabu']=tabus[-1]
        log.append(row);write(root/'log.json',log);write(root/'valid_cuts.json',cuts)
        print(e.pid,'C2',it,row['action'],flush=True)
    write(root/'result.json',dict(pid=e.pid,witnesses=witnesses,iterations=log,valid_cuts=cuts,heuristic_tabus=tabus,
        infeasibility_proven=False,cut_scope='Unsplit atomic tasks and 118 frozen sites; no solver timeout used as infeasibility cut'))
if __name__=='__main__':main()
