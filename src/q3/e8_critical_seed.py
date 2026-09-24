"""Bounded alternate partitions of early hard-deadline communication tasks."""
from src.q3.e8_seed_variants import *

def run(gamma):
    e=load_engine(gamma);dest=gamma_dir(gamma)
    units={s:list(f.atomic_task_id) for s,f in e.atoms.groupby('transport_sortie_id')}
    old=json.loads((dest/'candidate_search.json').read_text());e.search_log=old['searches']
    for names in [['M001'],['M003','M006','M007'],['M004','M008'],['M002','M005']]:
        ids=sum((units[s] for s in names),[])
        e.search_common(ids,max_checks=2500,wanted=6,rank='origin')
    e.save()
    early=[s for s in units if int(s[1:])<=8];partitions=[]
    def recurse(left,groups):
        if len(groups)>5:return
        if not left:partitions.append(groups);return
        first=left[0]
        for n in range(len(left)-1,-1,-1):
            for rest in itertools.combinations(left[1:],n):
                names=[first]+list(rest);ids=sum((units[s] for s in names),[]);common=e.common(ids)
                if not common:continue
                sid=min(common,key=lambda s:e.energy(e.sites[s],0)['outbound_time_s']+e.energy(e.sites[s],0)['return_time_s'])
                recurse([s for s in left if s not in names],groups+[dict(site_id=sid,task_ids=ids)])
    recurse(early,[]);partitions.sort(key=lambda gs:(len(gs),sum(e.energy(e.sites[g['site_id']],0)['total_energy_kwh'] for g in gs)))
    later=[]
    for start in [9,17,25]:
        ids=[a for a in e.atoms.index if start<=int(e.atoms.loc[a].transport_sortie_id[1:])<start+8]
        if ids:later+=partition(e,ids,'unit')
    log=[]
    for i,earlygroups in enumerate(partitions[:100]):
        groups=earlygroups+later
        ans,info=relay_order_milp(e,groups,limit=5)
        if info['status']!=2:ans,joint=relay_order_milp(e,groups,limit=60,joint_resources=True);info['joint']=joint
        info['groups_definition']=groups;log.append(info);write_json(dest/'critical_partition_search.json',dict(total_partitions=len(partitions),attempts=log))
        print('CRITICAL',gamma,i,len(earlygroups),info['status'],info.get('joint'),flush=True)
        if ans:
            ans['Gamma_C_db']=gamma;write_json(dest/'seed.json',ans);return ans

if __name__=='__main__':
    import sys
    run(float(sys.argv[1]))
