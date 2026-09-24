"""Deterministic bounded L1 neighborhoods; official objectives select witnesses."""
from src.q3.e7_core import *


def group_key(groups):return tuple((g['site_id'],tuple(sorted(g['task_ids']))) for g in groups)


def neighbors(e,pid,result,allow_split=True):
    groups=result['groups'];seq=result['sequences'];seen=set()
    def unique(gs,ss,kind):
        key=(group_key(gs),tuple(tuple(x) for x in ss))
        if key in seen:return None
        seen.add(key);return gs,ss,kind
    for src in range(2):
        for at,job in enumerate(seq[src]):
            for dst in range(2):
                for pos in range(len(seq[dst])+1):
                    ss=[list(x) for x in seq];ss[src].pop(at);ss[dst].insert(min(pos,len(ss[dst])),job)
                    v=unique(groups,ss,'RELAY_ORDER_INSERT')
                    if v:yield v
    def site_cost(sid):
        en=e.energy(e.sites[sid],0);return en['outbound_time_s']+en['return_time_s']
    def common(ids):return set.intersection(*(set(e.edges[pid][a]) for a in ids))
    for j,g in enumerate(groups):
        for sid in sorted(common(g['task_ids']),key=lambda s:(site_cost(s),s))[:3]:
            if sid==g['site_id'] or not all(e.check_task(a,sid) for a in g['task_ids']):continue
            gs=[dict(x) for x in groups];gs[j]=dict(site_id=sid,task_ids=g['task_ids'])
            v=unique(gs,seq,'COMMON_SITE_REPLACEMENT')
            if v:yield v
    for r in range(2):
        for i,j in zip(seq[r][:-1],seq[r][1:]):
            tasks=sorted(groups[i]['task_ids']+groups[j]['task_ids'])
            for sid in sorted(common(tasks),key=lambda s:(site_cost(s),s))[:3]:
                if not all(e.check_task(a,sid) for a in tasks):continue
                gs=[];mapping={}
                for k,g in enumerate(groups):
                    if k==j:continue
                    mapping[k]=len(gs);gs.append(dict(site_id=sid,task_ids=tasks) if k==i else g)
                ss=[[mapping[k] for k in s if k!=j] for s in seq]
                v=unique(gs,ss,'ADJACENT_COMMON_SITE_MERGE')
                if v:yield v
    if allow_split:
        for j,g in enumerate(groups):
            units={}
            for a in g['task_ids']:units.setdefault(e.atoms.loc[a].transport_sortie_id,[]).append(a)
            if len(units)<2:continue
            for sid,tasks in sorted(units.items()):
                rest=sorted(set(g['task_ids'])-set(tasks));gs=[dict(x) for x in groups]
                gs[j]=dict(site_id=g['site_id'],task_ids=rest);new=len(gs)
                gs.append(dict(site_id=g['site_id'],task_ids=tasks))
                ss=[list(s) for s in seq]
                for s in ss:
                    if j in s:s.insert(s.index(j)+1,new);break
                v=unique(gs,ss,'SPLIT_TRANSPORT_UNITS')
                if v:yield v


def search(e,seed,objective='timeliness',late_budget=None,rounds=3,repairs_per_round=24,label='search',fixed_transport_order=False):
    tick=time.monotonic();pid=seed['pareto_id'];cache={};archive=[];history=[];evaluated=0
    def timing(gs):
        key=group_key(gs)
        if key not in cache:cache[key]=Timing(e,pid,gs,objective,late_budget,fixed_transport_order)
        return cache[key]
    initial=timing(seed['groups']).solve(seed['sequences'],node_limit=0)
    if initial is None:
        # A seed with the same epsilon budget is still a valid incumbent even
        # when this bounded resource allocator misses its known assignment.
        if late_budget is None or seed['metrics']['J_late']<=late_budget+1e-4:initial=seed
        else:return None,[],dict(status='NO_FEASIBLE_SEED')
    best=initial;archive.append(best)
    for iteration in range(rounds):
        ranked=[]
        for gs,ss,kind in neighbors(e,pid,best):
            model=timing(gs);relax=model.lp(ss,());evaluated+=1
            if relax is None:continue
            x,bound=relax
            if objective=='timeliness' and bound>best['metrics']['J_late']+1e-5:continue
            if objective=='makespan' and bound>best['metrics']['joint_makespan_s']+1e-5:continue
            rank=(len(gs),bound) if objective=='relay_sorties' else (bound,len(gs))
            ranked.append((rank,len(ranked),gs,ss,kind))
        ranked.sort(key=lambda x:(x[0],x[1]));winner=best;feasible=0
        for _,_,gs,ss,kind in ranked[:repairs_per_round]:
            answer=timing(gs).solve(ss,node_limit=0)
            if answer is None:continue
            feasible+=1;answer['move']=kind;archive.append(answer)
            if improves(answer,winner,objective):winner=answer
        history.append(dict(iteration=iteration+1,ranked=len(ranked),repaired=min(len(ranked),repairs_per_round),
                            feasible=feasible,metrics=winner['metrics'],elapsed_s=time.monotonic()-tick))
        print(label,history[-1],flush=True)
        if not improves(winner,best,objective):break
        best=winner
    best=dict(best,objective=objective,J_late_budget=late_budget)
    return best,archive,dict(status='BOUNDED_SEARCH_COMPLETED',objective=objective,J_late_budget=late_budget,
        rounds=rounds,repairs_per_round=repairs_per_round,root_relaxations=evaluated,
        lp_solves=sum(t.lp_solves for t in cache.values()),runtime_s=time.monotonic()-tick,history=history,
        global_optimum_proven=False,fixed_transport_order=fixed_transport_order,
        energy_ranking_surrogate='FLIGHT_PLUS_CONTINUOUS_ACTIVE_SPAN; ACCEPTANCE_USES_EXACT_UNION_ENERGY')


if __name__=='__main__':
    e=engine_for();seed=json.loads((OUT/'free_order_seed.json').read_text())
    best,archive,info=search(e,seed,rounds=4,repairs_per_round=28,label='TIMELINESS')
    write_json(OUT/'best_timeliness.json',best);write_json(OUT/'timeliness_archive.json',archive);write_json(OUT/'timeliness_search.json',info)
