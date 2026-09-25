"""Historical c13306e uniform operators, with explicit preference comparisons."""
import copy
from src.q2 import operators
from src.q2.evaluator_sol import evaluate_solution

def search(base,rng,ev,decoder,pref,remaining,save):
    current=base;archive=[base];iteration=0
    original=operators._repair_key
    operators._repair_key=lambda sol:pref.key(sol.metrics,'historical_repair_candidate')
    try:
        while remaining()>.5:
            current=min(archive,key=lambda sol:pref.key(sol.metrics,'archive_selection'))
            d=rng.choice(list(operators.DESTROY));r=rng.choice(list(operators.REPAIR));fn=operators.DESTROY[d]
            pref.event('operator_selection',destroy=d,repair=r,adaptive=False,historical_five_destroy_three_repair=True)
            ms,loose=fn(current.missions,rng,ev) if d in ['worst_timeliness_removal','related_service_removal'] else fn(current.missions,rng)
            sol=operators.REPAIR[r](ms,loose,rng,ev,decoder);iteration+=1
            if sol:
                save(sol.decoded,'HISTORICAL_UNIFORM_WITH_PREFERENCE_INTERFACE');archive.append(sol)
                accept=pref.key(sol.metrics,'accept_candidate')<pref.key(current.metrics,'accept_incumbent') or rng.random()<.1
                pref.event('acceptance',accepted=accept,nonimprovement_probability=.1)
                if accept:current=sol
            if iteration%4==0:
                raw=copy.deepcopy(current.missions);rng.shuffle(raw);sol=evaluate_solution(raw,ev,decoder,preserve_order=True)
                if sol:save(sol.decoded,'HISTORICAL_EXPLICIT_ORDER');archive.append(sol)
            pref.next()
    finally:operators._repair_key=original
