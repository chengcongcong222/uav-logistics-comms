"""Deterministic regrouping seeds; transport routes remain fixed."""
from src.q3.e8_search import *

def partition(e,ids,mode):
    units=[]
    for sid,frame in e.atoms.loc[ids].groupby('transport_sortie_id'):
        aa=list(frame.atomic_task_id)
        if mode!='atomic' and e.common(aa):units.append(aa)
        else:units.extend([[a] for a in aa])
    groups=[]
    while units:
        options=[]
        for site in sorted(set.union(*(e.common(u) for u in units))):
            covered=[i for i,u in enumerate(units) if site in e.common(u)]
            duration=sum(float(e.atoms.loc[a].service_duration_s) for i in covered for a in units[i])
            en=e.energy(e.sites[site],0)
            score=(-len(covered),en['outbound_time_s']+en['return_time_s']) if mode!='duration' else (-duration,en['outbound_time_s']+en['return_time_s'])
            options.append((score,site,covered))
        _,site,covered=min(options)
        groups.append(dict(site_id=site,task_ids=sorted(a for i in covered for a in units[i])))
        units=[u for i,u in enumerate(units) if i not in covered]
    return groups

def variants(e):
    # Early hard-deadline tasks must be allowed to share new sites with tasks
    # absent from the old zero-margin demands; old E7 groups are not sacred.
    for mode in ['unit','atomic','duration']:
        for batch in [6,8,12,28]:
            groups=[]
            for start in range(1,29,batch):
                ids=[a for a in e.atoms.index if start<=int(e.atoms.loc[a].transport_sortie_id[1:])<start+batch]
                if ids:groups+=partition(e,ids,mode)
            yield f'{mode}_batch{batch}',groups

def run(gamma):
    e=load_engine(gamma);log=[];answers=[]
    for name,groups in variants(e):
        if 'batch6' in name or 'batch28' in name:continue
        ans,info=relay_order_milp(e,groups,limit=60,joint_resources=True)
        info.update(name=name,groups_definition=groups);log.append(info)
        write_json(gamma_dir(gamma)/'regrouping_search.json',log)
        print(gamma,name,len(groups),info,flush=True)
        if ans:
            ans['Gamma_C_db']=gamma;answers.append(ans)
            write_json(gamma_dir(gamma)/'seed.json',min(answers,key=lambda r:objective_key(r,'timeliness')))
            write_json(gamma_dir(gamma)/'regrouping_feasible.json',answers)
            if len(answers)>=3:break
    return answers

if __name__=='__main__':
    import sys
    run(float(sys.argv[1]))
