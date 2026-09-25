"""Exhaustive <=3 frozen-site cover, independent of generated relay groups."""
import itertools
import pandas as pd
from src.bench_p1_4.common import *

def main():
    rows=[]
    for root in (OUT/'screening').iterdir():
        f=root/'q3'/root.name/'candidate_pairs.csv'
        if not f.exists():continue
        d=pd.read_csv(f);a=pd.read_csv(f.parent/'guarded_atomic_tasks.csv');ids=list(a.atomic_task_id);full=(1<<len(ids))-1;masks={}
        for site,r in d.groupby('site_id'):masks.setdefault(sum(1<<ids.index(t) for t in set(r.atomic_task_id)),site)
        found=None
        for k in [1,2,3]:
            for c in itertools.combinations(masks,k):
                u=0
                for x in c:u|=x
                if u==full:found=[masks[x] for x in c];break
            if found:break
        rows.append(dict(pid=root.name,site_masks=len(masks),minimum_distinct_sites=len(found) if found else None,
            relay_sorties_lower_bound=len(found) if found else 4,example_cover=found,
            scope='Full frozen task-site relation, unsplit atoms; necessary flight-count bound, arbitrary timing. Exact <=3 site set-cover enumeration, not a makespan proof.'))
    write(OUT/'site_cover_bounds.json',rows)
if __name__=='__main__':main()
