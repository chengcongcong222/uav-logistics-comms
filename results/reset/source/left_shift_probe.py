"""Continuous earliest-start polish for the already assigned resource orders.
This removes conservative grid waiting WITHOUT changing loads/types/IDs/energy.
It is not global scheduling optimization; the resource sequences stay fixed.
"""
import json,sys
from pathlib import Path
from collections import defaultdict
p=Path(sys.argv[1]);sol=json.loads(p.read_text());edges=[]
for field,at_takeoff in [('uav_id',False),('battery_id',True)]:
 by=defaultdict(list)
 for i,m in enumerate(sol):by[m[field]].append(i)
 for inds in by.values():
  inds.sort(key=lambda i:sol[i]['start']+(sol[i]['prep'] if at_takeoff else 0))
  for i,j in zip(inds,inds[1:]):
   weight=sol[i]['duration']+(sol[i]['charge']-sol[j]['prep'] if at_takeoff else 0)
   edges.append((i,j,weight))
s=[0.0]*len(sol)
for _ in range(len(sol)+1):
 changed=False
 for i,j,w in edges:
  if s[j]+1e-9<s[i]+w:
   s[j]=s[i]+w;changed=True
 if not changed:break
else:raise RuntimeError('positive cycle')
for i,m in enumerate(sol):
 assert s[i]<=m['start']+1e-6
 m['unpolished_start_s']=m['start'];m['start']=s[i]
out=p.with_name(p.stem.replace('_schedule','_polished_schedule')+'.json')
out.write_text(json.dumps(sol,ensure_ascii=False,indent=2));print(out)
