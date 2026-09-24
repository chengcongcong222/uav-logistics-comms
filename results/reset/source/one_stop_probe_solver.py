"""Independent Q2 feasibility/quality probe, NOT a full problem-D solver.
Own source workbook data; 15 roundtrip geometries from repository badc8a4.
Enumerates material-equivalent one-stop loads, then time-indexed MILP.
All expected deadlines are imposed in this ZERO-LATE feasibility experiment.
Resource intervals are rounded OUTWARD to the configured start-grid cells, not relaxed.
No competitor schedule/code is used. Full Q3 communication is NOT modeled.
"""
from pathlib import Path
import csv,json,math,itertools,time,argparse
from collections import defaultdict,Counter
import numpy as np
from scipy.optimize import milp,Bounds,LinearConstraint
from scipy.sparse import coo_matrix
ROOT=Path(__file__).resolve().parent

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--limit',type=float,default=25)
 ap.add_argument('--horizon',type=int,default=10800);ap.add_argument('--step',type=int,default=60)
 ap.add_argument('--pool',choices=['all','local'],default='all')
 ap.add_argument('--objective',choices=['energy','sorties'],default='energy')
 args=ap.parse_args(); tick=args.step;H=args.horizon;nc=math.ceil((H+4000)/tick)
 data=json.loads((ROOT/'probe_inputs.json').read_text())
 trs=data['运输无人机数据.xlsx']['sheet0'];ty={r[0]:r for r in trs[2:5]}
 inv={'A':4,'B':2,'C':2};batt={r[0]:(int(r[1]),float(r[2])) for r in trs[19:22]}
 geo={r['service']:{k:float(v) for k,v in r.items() if k!='service'} for r in csv.DictReader((ROOT/'one_stop_geometry_snapshot.csv').open())}
 groups=defaultdict(list)
 for r in data['逐箱'][1:]:
  if not r[0]:continue
  # Only genuinely interchangeable boxes are grouped.
  d=min(float(r[7]),float(r[6]) if r[5]=='是' and r[6] else math.inf)
  key=(r[1],r[2],float(r[3]),float(r[4]),d,float(r[8]))
  groups[key].append(r)
 keys=list(groups); cidx={k:i for i,k in enumerate(keys)};C=len(keys)
 byservice=defaultdict(list)
 for k in keys:byservice[k[0]].append(k)
 patterns=[]
 for svc,ks in sorted(byservice.items()):
  gg=geo[svc];d=gg['distance_m'];up=gg['up_m'];down=gg['down_m']
  for counts in itertools.product(*[range(len(groups[k])+1) for k in ks]):
   n=sum(counts)
   if not n:continue
   mass=sum(nk*k[2] for nk,k in zip(counts,ks));vol=sum(nk*k[3] for nk,k in zip(counts,ks))
   deadline=min(k[4] for nk,k in zip(counts,ks) if nk)
   for g,r in ty.items():
    m0,Q,V,v,L0,LF,Eu,rr,prep,load,base,per,vu,vd,eta=[float(x) for x in r[2:17]]
    if mass>Q+1e-10 or vol>V+1e-10:continue
    L=L0-(L0-LF)*(mass/Q)**1.5
    E=Eu*d/L+Eu*d/L0+9.80665*((m0+mass)*up+m0*down)/(eta*3.6e6)
    if E>(1-rr/100)*Eu+1e-10:continue
    prepall=prep+load*n;hand=base+per*n
    flyout=up/vu+d/v+down/vd;flyback=down/vu+d/v+up/vd
    delivery=prepall+flyout+hand;duration=delivery+flyback
    soc=1-E/Eu;tf=batt[g][1]
    charge=tf*(.65*(.9-soc)/.9+.35) if soc<.9 else tf*.35*(1-soc)/.1
    if delivery>deadline:continue
    patterns.append(dict(service=svc,type=g,counts=[(cidx[k],nk) for k,nk in zip(ks,counts) if nk],
       mass=mass,volume=vol,n=n,energy=E,prep=prepall,delivery=delivery,duration=duration,charge=charge,
       latest=min(deadline-delivery,H-duration)))
 if args.pool=='local':
  # Own exact single-service partitions generate a compact initial pool.
  # This is deliberately incomplete candidate generation, never a safe deletion claim.
  keep=set()
  for svc in sorted(byservice):
   ci=[cidx[k] for k in byservice[svc]];dem=np.array([len(groups[keys[i]]) for i in ci])
   for allowed in ['ABC','A','B','C']:
    inds=[i for i,p in enumerate(patterns) if p['service']==svc and p['type'] in allowed]
    if not inds:continue
    aa=np.zeros((len(ci),len(inds))); local={c:i for i,c in enumerate(ci)}
    for jj,ii in enumerate(inds):
     for c,nk in patterns[ii]['counts']:aa[local[c],jj]=nk
    for ob in ['energy','number','duration','battery']:
     costs=np.array([patterns[i]['energy'] if ob=='energy' else (1000+patterns[i]['energy']) if ob=='number' else patterns[i]['duration']+(patterns[i]['charge'] if ob=='battery' else 0) for i in inds])
     rr=milp(costs,integrality=np.ones(len(inds)),bounds=Bounds(0,8),constraints=LinearConstraint(aa,dem,dem),options={'time_limit':.5})
     if rr.x is not None:keep.update(inds[j] for j,v in enumerate(rr.x) if v>.5)
  # Always include standalone boxes, so every type remains reachable where physically feasible.
  keep.update(i for i,p in enumerate(patterns) if p['n']==1)
  patterns=[patterns[i] for i in sorted(keep)]
 print('patterns',len(patterns),'classes',C,flush=True)
 (ROOT/'one_stop_pattern_pool.json').write_text(json.dumps({'patterns':patterns,'groups':[[list(k),v] for k,v in groups.items()]},ensure_ascii=False))
 rows=[];cols=[];vals=[];obj=[];meta=[];ub=[]
 for pi,p in enumerate(patterns):
  if p['latest']<0:continue
  for st in range(0,int(math.floor(p['latest']/tick))+1):
   j=len(obj);s=st*tick;end=s+p['duration'];bstart=s+p['prep'];bend=end+p['charge'];gi='ABC'.index(p['type'])
   for ci,nk in p['counts']:rows.append(ci);cols.append(j);vals.append(nk)
   # Outward occupied-cell rounding is sufficient, albeit conservative.
   for t in range(st,math.ceil(end/tick-1e-12)):
    rows.append(C+gi*nc+t);cols.append(j);vals.append(1)
   for t in range(math.floor(bstart/tick+1e-12),math.ceil(bend/tick-1e-12)):
    rows.append(C+3*nc+gi*nc+t);cols.append(j);vals.append(1)
   obj.append(p['energy'] if args.objective=='energy' else 1.0)
   meta.append((pi,s));ub.append(min(inv[p['type']],min(len(groups[keys[ci]])//nk for ci,nk in p['counts'])))
 m=C+6*nc;n=len(obj);print('variables',n,'rows',m,'nnz',len(vals),flush=True)
 A=coo_matrix((vals,(rows,cols)),shape=(m,n)).tocsc()
 demand=np.array([len(groups[k]) for k in keys]);lower=np.r_[demand,np.full(6*nc,-np.inf)]
 upper=np.r_[demand,*[np.full(nc,inv[g]) for g in 'ABC'],*[np.full(nc,batt[g][0]) for g in 'ABC']]
 start=time.monotonic()
 res=milp(np.array(obj),integrality=np.ones(n),bounds=Bounds(np.zeros(n),np.array(ub)),constraints=LinearConstraint(A,lower,upper),
  options={'time_limit':args.limit,'mip_rel_gap':.01,'disp':True,'presolve':False})
 print('status',res.status,res.message,flush=True)
 name=f'one_stop_h{H}_t{tick}_{args.objective}_{args.pool}'
 summary={'status':int(res.status),'message':res.message,'runtime_s':time.monotonic()-start,'patterns':len(patterns),
  'variables':n,'start_grid_s':tick,'horizon_s':H,'objective':args.objective,'source_commit':'badc8a4282f9935018c837e52b32b86539c96071',
  'scope':'single-stop zero-late conservative time-indexed candidate model; not original optimum'}
 if res.x is not None:
  summary.update(objective_value=float(res.fun),dual_bound=float(res.mip_dual_bound),mip_gap=float(res.mip_gap))
  assigned=[];remaining={i:list(groups[k]) for i,k in enumerate(keys)}
  for j,vv in enumerate(res.x):
   for _ in range(int(round(vv))):
    pi,s=meta[j];p=patterns[pi];boxes=[]
    for ci,nn in p['counts']:
     for _ in range(nn): boxes.append(remaining[ci].pop())
    assigned.append(dict(**p,start=s,boxes=[b[0] for b in boxes]))
  assert all(not v for v in remaining.values())
  # Independent assignment by exact interval coloring; no permanent UAV/battery binding.
  for g in 'ABC':
   ids=[i for i,p in enumerate(assigned) if p['type']==g]
   uend=[0.0]*inv[g];bend=[0.0]*batt[g][0]
   for i in sorted(ids,key=lambda i:assigned[i]['start']):
    p=assigned[i];v=min(range(len(uend)),key=lambda k:uend[k]);assert uend[v]<=p['start']+1e-7
    p['uav_id']=f'{g}-U{v+1}';uend[v]=p['start']+p['duration']
   for i in sorted(ids,key=lambda i:assigned[i]['start']+assigned[i]['prep']):
    p=assigned[i];v=min(range(len(bend)),key=lambda k:bend[k]);assert bend[v]<=p['start']+p['prep']+1e-7
    p['battery_id']=f'{g}-B{v+1}';bend[v]=p['start']+p['duration']+p['charge']
  summary.update(sorties=len(assigned),energy_kwh=sum(p['energy'] for p in assigned),makespan_s=max(p['start']+p['duration'] for p in assigned))
  (ROOT/f'{name}_schedule.json').write_text(json.dumps(assigned,ensure_ascii=False,indent=2))
 (ROOT/f'{name}_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
 print(json.dumps(summary,ensure_ascii=False),flush=True)
if __name__=='__main__':main()
