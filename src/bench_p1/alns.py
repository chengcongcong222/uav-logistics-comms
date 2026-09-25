"""Problem-specific adaptive LNS; not a reproduction of the PDPTW paper."""
import copy,math
from src.q2.evaluator_sol import evaluate_solution,pack_key
from src.q2.operators import _insert_box,_remove_boxes,_boxes_of

class Adaptive:
    def __init__(self,names,reaction=.25):
        self.weights={n:1. for n in names};self.reaction=reaction;self.history=[]
    def choose(self,rng):return rng.choices(list(self.weights),weights=list(self.weights.values()))[0]
    def update(self,name,reward):
        old=self.weights[name];self.weights[name]=max(.05,(1-self.reaction)*old+self.reaction*reward)
        self.history.append(dict(operator=name,old=old,reward=reward,new=self.weights[name]))

def destroy(sol,kind,rng,ev):
    ids=_boxes_of(sol.missions);k=min(2,len(ids))
    if kind=='random':removed=rng.sample(ids,k)
    elif kind=='timeliness':
        delivered={b:m.delivery_times_s[s] for m in sol.decoded for s,bb in m.boxes_by_service.items() for b in bb}
        removed=sorted(ids,key=lambda b:float(ev.box_idx.loc[b].priority_weight)*delivered[b]/float(ev.box_idx.loc[b].expected_deadline_s),reverse=True)[:k]
    else:
        b=rng.choice(ids);svc=ev.box_idx.loc[b].service_id;nodes=ev.nodes.set_index('node_id');x=nodes.loc[svc]
        def distance(q):
            row=ev.box_idx.loc[q];n=nodes.loc[row.service_id]
            return math.hypot(n.x_m-x.x_m,n.y_m-x.y_m)+.01*abs(row.expected_deadline_s-ev.box_idx.loc[b].expected_deadline_s)
        removed=sorted(ids,key=distance)[:k]
    return _remove_boxes(copy.deepcopy(sol.missions),set(removed))

def repair(ms,loose,kind,rng,ev,decoder,pref,remaining):
    ms=copy.deepcopy(ms);loose=list(loose)
    while loose:
        choices=[]
        for b in loose:
            options=[]
            for raw in _insert_box(ev,ms,b,rng,'same'):
                if remaining()<.5:raise TimeoutError('repair budget')
                sol=evaluate_solution(raw,ev,decoder)
                if sol:options.append((pref.key(sol.metrics,'repair_candidate'),sol))
            if not options:continue
            options.sort(key=lambda x:x[0]);first=options[0];second=options[min(1,len(options)-1)]
            regret=tuple(y-x for x,y in zip(first[0],second[0]))
            choices.append((b,first,regret))
        if not choices:return None
        chosen=max(choices,key=lambda x:(x[2],tuple(-v for v in x[1][0]))) if kind=='regret2' else min(choices,key=lambda x:x[1][0])
        b,(_,sol),_=chosen;pref.event('repair_selection',box_id=b,repair=kind);ms=sol.missions;loose.remove(b)
    return evaluate_solution(ms,ev,decoder)

def local_candidates(sol,rng,ev,decoder,pref,remaining):
    """Explicit order, all alternative types for one mission, and box split."""
    raw=copy.deepcopy(sol.missions);i=rng.randrange(len(raw));trials=[]
    if len(raw)>1:
        ordered=copy.deepcopy(raw);m=ordered.pop(i);ordered.insert(rng.randrange(len(ordered)+1),m);trials.append(('order',ordered,True))
    for typ in ev.types.index:
        if typ!=raw[i]['uav_type']:
            x=copy.deepcopy(raw);x[i]['uav_type']=typ;trials.append(('type',x,False))
    boxids=_boxes_of([raw[i]])
    if len(boxids)>1:
        b=rng.choice(boxids);x,loose=_remove_boxes(copy.deepcopy(raw),{b});svc=ev.box_idx.loc[b].service_id
        x.append(pack_key(raw[i]['uav_type'],[svc],{svc:[b]}));trials.append(('split',x,False))
    answer=sol
    for name,raw,ordered in trials:
        if remaining()<.5:raise TimeoutError('local budget')
        cand=evaluate_solution(raw,ev,decoder,preserve_order=ordered)
        if cand and pref.key(cand.metrics,'local_'+name)<pref.key(answer.metrics,'local_incumbent'):answer=cand
    return answer

def search(base,rng,ev,decoder,pref,remaining,save,adaptive=True):
    d=Adaptive(['random','timeliness','related']);r=Adaptive(['greedy','regret2']);current=base;archive=[base];iteration=0
    while remaining()>1:
        # A common preference is used for archive selection, all repair choices,
        # local moves and acceptance in this iteration.
        current=min(archive,key=lambda s:pref.key(s.metrics,'archive_selection'))
        dn=list(d.weights)[iteration%3] if iteration<3 else (d.choose(rng) if adaptive else rng.choice(list(d.weights)))
        rn=list(r.weights)[iteration%2] if iteration<2 else (r.choose(rng) if adaptive else rng.choice(list(r.weights)))
        pref.event('operator_selection',destroy=dn,repair=rn,adaptive=adaptive,destroy_weights=d.weights,repair_weights=r.weights)
        ms,loose=destroy(current,dn,rng,ev);cand=repair(ms,loose,rn,rng,ev,decoder,pref,remaining);reward=.1;accepted=False
        if cand:
            cand=local_candidates(cand,rng,ev,decoder,pref,remaining)
            new=pref.key(cand.metrics,'accept_candidate');old=pref.key(current.metrics,'accept_incumbent')
            best=min(pref.key(s.metrics,'reward_reference') for s in archive)
            temp=.05*.995**iteration
            accepted=new<old or (new[:2]==old[:2] and rng.random()<math.exp(-max(0,new[2]-old[2])/temp))
            reward=8 if new<best else 4 if new<old else 1 if accepted else .1
            save(cand.decoded,'ADAPTIVE_LNS' if adaptive else 'UNIFORM_LNS')
            archive.append(cand)
            if accepted:current=cand
        if adaptive:d.update(dn,reward);r.update(rn,reward)
        pref.event('acceptance',accepted=accepted,reward=reward,temperature=.05*.995**iteration,destroy_weights=d.weights,repair_weights=r.weights)
        iteration+=1;pref.next()
