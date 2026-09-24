"""Independent audit: no imports from the candidate generator or optimizer.
Uses original workbook cell-value snapshot + frozen repository roundtrip geometry.
Recomputes boxes, physical loads/time/energy, deadlines and actual resource IDs.
Does NOT perform a new DEM audit or evaluate Q3 communication.
"""
from pathlib import Path
import json,csv,math,argparse,hashlib
from collections import Counter,defaultdict
R=Path(__file__).resolve().parent

def validate(path):
 data=json.loads((R/'probe_inputs.json').read_text()); box={b[0]:b for b in data['逐箱'][1:] if b[0]}
 tab=data['运输无人机数据.xlsx']['sheet0']; types={r[0]:r for r in tab[2:5]};bat={r[0]:r for r in tab[19:22]}
 geometry={row['service']:row for row in csv.DictReader((R/'one_stop_geometry_snapshot.csv').open())}
 sol=json.loads(path.read_text()); used=Counter(b for p in sol for b in p['boxes'])
 assert used==Counter({b:1 for b in box}), 'Coverage error'
 umax={'A':4,'B':2,'C':2}; ucal=defaultdict(list);bcal=defaultdict(list)
 late=norm=weight=energy=0.;latest=0.;margin=math.inf;hard_margin=math.inf;hard_count=0;deliveries=[];sorties=[]
 error_time=error_energy=0.
 for i,p in enumerate(sol,1):
  ids=p['boxes'];bs=[box[b] for b in ids];g=p['type'];svc=p['service'];r=types[g];gg=geometry[svc]
  assert all(b[1]==svc for b in bs)
  mass=sum(float(b[3]) for b in bs);vol=sum(float(b[4]) for b in bs);count=len(bs)
  assert mass<=r[3]+1e-9 and vol<=r[4]+1e-9
  dist=float(gg['distance_m']);H=float(gg['cruise_m']);z0=float(gg['origin_m']);zi=float(gg['dest_m'])
  # Rebuild two directed legs using endpoint elevations rather than stored h+/-.
  legs=[(z0,zi,mass),(zi,z0,0.)];ts=[];es=[]
  for origin,dest,q in legs:
   climb=max(0.,H-origin);descent=max(0.,H-dest)
   duration=climb/r[14]+dist/r[5]+descent/r[15]
   rate=r[8]/(r[6]-(r[6]-r[7])*(q/r[3])**1.5)
   e=dist*rate+(r[2]+q)*9.80665*climb/r[16]/3600000.
   ts.append(duration);es.append(e)
  prep=r[10]+count*r[11];handover=r[12]+count*r[13]
  s=float(p['start']);to=s+prep;de=to+ts[0]+handover;end=de+ts[1];e=sum(es);soc=1-e/r[8]
  assert s>=0 and soc>=r[9]/100-1e-10
  # Integral of piecewise charge-time rate, independent expression.
  chg=bat[g][2]*(max(0.,.9-soc)*.65/.9+(1-max(soc,.9))*.35/.1)
  error_energy=max(error_energy,abs(e-p['energy']))
  error_time=max(error_time,abs((end-s)-p['duration']),abs((de-s)-p['delivery']),abs(chg-p['charge']))
  assert error_energy<1e-8 and error_time<1e-6
  assert p['uav_id'].startswith(g+'-U') and p['battery_id'].startswith(g+'-B'), 'Resource type mismatch'
  u=int(p['uav_id'].split('-U')[1]);bnum=int(p['battery_id'].split('-B')[1]);assert 1<=u<=umax[g] and 1<=bnum<=bat[g][1]
  ucal[(g,u)].append((s,end,i));bcal[(g,bnum)].append((to,end+chg,i))
  minslack=math.inf
  for b in bs:
   due=float(b[7]);w=float(b[8]);dl=[]
   if b[2]=='医疗物资':dl.append(due)
   if b[5]=='是':dl.append(float(b[6]))
   if dl:
    hard_count+=1;assert de<=min(dl)+1e-6;hard_margin=min(hard_margin,min(dl)-de)
   assert de<=due+1e-6, f'nonzero tardiness: {b[0]}'
   tard=max(0.,de-due);late+=w*tard;norm+=w*de/due;weight+=w;minslack=min(minslack,due-de)
   deliveries.append(dict(box_id=b[0],service_id=svc,sortie_id=f'R{i:03d}',delivery_time_s=de,expected_deadline_s=due,hard_deadline_s=min(dl) if dl else None,priority=w))
  latest=max(latest,end);energy+=e;margin=min(margin,(1-r[9]/100)*r[8]-e)
  sorties.append(dict(sortie_id=f'R{i:03d}',uav_type=g,uav_id=f'U{(u if g=="A" else u+4 if g=="B" else u+6):02d}',battery_id=f'BAT-{g}-{bnum:02d}',service_sequence=f'O01>{svc}>O01',box_ids=';'.join(ids),mass_kg=mass,volume_m3=vol,preparation_start_s=s,takeoff_s=to,delivery_s=de,return_s=end,energy_kwh=e,return_soc=soc,battery_ready_s=end+chg))
 for cal in [ucal,bcal]:
  for resource,ivs in cal.items():
   ivs.sort()
   for a,b in zip(ivs,ivs[1:]):assert a[1]<=b[0]+1e-7,(resource,a,b)
 summary=dict(status='INDEPENDENT_SINGLE_STOP_Q2_AUDIT_PASS',boxes=len(box),hard_deadline_boxes=hard_count,
  first_batch_boxes=sum(b[5]=='是' for b in box.values()),total_mass_kg=sum(b[3] for b in box.values()),
  total_volume_m3=sum(b[4] for b in box.values()),J_late=late,J_norm=norm/weight,makespan_s=latest,
  energy_kwh=energy,sorties=len(sol),by_type=dict(Counter(p['type'] for p in sol)),
  minimum_energy_margin_kwh=margin,minimum_hard_deadline_margin_s=hard_margin,resource_conflicts=0,
  energy_recompute_max_error=error_energy,time_recompute_max_error=error_time,
  limits='Independent Q2 audit under repository frozen geometry and accepted formulas; NOT a fresh DEM audit; NOT Q3 communication; NOT original global optimum.',
  source_commit='badc8a4282f9935018c837e52b32b86539c96071',schedule_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
 out=path.with_name(path.stem.replace('_schedule','')+'_audit.json');out.write_text(json.dumps(summary,ensure_ascii=False,indent=2))
 for name,rows in [('sorties',sorties),('deliveries',deliveries)]:
  dst=path.with_name(path.stem.replace('_schedule','')+'_'+name+'.csv')
  with dst.open('w',newline='',encoding='utf-8-sig') as f:
   wr=csv.DictWriter(f,fieldnames=list(rows[0]));wr.writeheader();wr.writerows(rows)
 print(json.dumps(summary,ensure_ascii=False,indent=2));return summary
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('schedule',type=Path);args=ap.parse_args();validate(args.schedule)
