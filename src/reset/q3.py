"""G2 Q3: shared relative communication templates, fresh schedules per structure."""
import argparse,hashlib,json,math
import numpy as np
import pandas as pd
from src.reset.geometry import ROOT,OUT,DATA,VERSION,FlightDem,write
from src.q3.e6_resources import ResourceEngine,read,write_csv,write_json,Q3
from src.q3.e52_geometry import SortieTrajectory
from src.q3.e8_candidates import RobustEngine
from src.q3.link_budget import fspl_db
from src.q3.terrain_los import blocked_line_cells
from src.q3.relay_candidate_generator import TF
from src.q3.relay_geometry import relay_route_energy_time
import src.xb1.q3 as previous
import src.q3.e7_core as core
import src.q3.e6_shift as shift
import src.q3.e6_export as exporter

class ResetEngine(RobustEngine):
    pool=previous.XBEngine.pool
    def __init__(self,pid):
        ResourceEngine.__init__(self);self.pid=pid;self.gamma=0.;self.search_log=[];self.geometry=FlightDem()
        self.base=OUT/'q2/pareto_schedules'/pid;self.dest=OUT/'q3'/pid;self.dest.mkdir(parents=True,exist_ok=True)
        inputs=[self.base/n for n in ['q2_sorties.csv','q2_box_delivery.csv','transport_trace.csv','missions.json']]+[DATA/'manifest.json',Path(__file__)]
        fingerprint={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs};manifest=self.dest/'cache_manifest.json'
        if manifest.exists():assert json.loads(manifest.read_text())==fingerprint,'G2 input/code changed; rebuild into fresh experiment'
        write(manifest,fingerprint)
        frame=read(self.base/'transport_trace.csv');self.access_cache.clear();self.position_cache.clear();self.edge_cache.clear()
        for sid in frame.task_id.unique():
            tr=SortieTrajectory(frame,pid,sid);self.trajectories[pid,sid]=tr;self.trajectories['P01',sid]=tr
        for p in sorted((Q3/'e8').glob('gamma_*/candidate_sites.csv'))+sorted((Q3/'e6').glob('candidate_sites_P*.csv')):
            for r in read(p).itertuples():self.add_site(r.x_m,r.y_m,r.agl_m)
        for s in self.sites.values():s.pop('static_energy',None)
        self.accepted_sites=set(self.sites);taskfile=self.dest/'guarded_atomic_tasks.csv'
        self.atoms=(read(taskfile) if taskfile.exists() else self.demands(frame)).set_index('atomic_task_id',drop=False)
        edges={a:{} for a in self.atoms.index};self.edges={pid:edges,'P01':edges}
        if (self.dest/'candidate_pairs.csv').exists():
            for r in read(self.dest/'candidate_sites.csv').itertuples():self.add_site(r.x_m,r.y_m,r.agl_m)
            for r in read(self.dest/'candidate_pairs.csv').to_dict('records'):edges[r['atomic_task_id']][r['site_id']]=r

    def energy(self,site,duration):
        if 'static_energy' not in site:
            o=self.origin;d=math.hypot(site['x_m']-o[0],site['y_m']-o[1]);z=self.geometry.maximum(o[:2],(site['x_m'],site['y_m']))['max_dem_m'];cruise=max(z+50,o[2],site['z_amsl_m']);up=cruise-o[2];back=cruise-site['z_amsl_m']
            en=relay_route_energy_time(self.pr,d,up,back,back,up,self.pr['setup_time_s'],0)
            en.update(horizontal_distance_m=d,max_dem_on_route_m=z,cruise_alt_m=cruise);site['static_energy']=en
        en=dict(site['static_energy']);en['service_energy_kwh']=(self.pr['hover_power_kw']+self.pr['comm_power_kw'])*duration/3600;en['total_energy_kwh']=en['flight_energy_kwh']+en['setup_energy_kwh']+en['service_energy_kwh'];en['energy_margin_kwh']=(1-self.pr['rho'])*self.pr['energy_kwh']-en['total_energy_kwh'];en['return_soc']=1-en['total_energy_kwh']/self.pr['energy_kwh'];return en

    def demands(self,frame):
        cache_root=OUT/'communication_templates';cache_root.mkdir(exist_ok=True);rows=[];log=[]
        specs={m['mission_id']:m for m in json.loads((self.base/'missions.json').read_text())};geometry_hash=hashlib.sha256((DATA/'manifest.json').read_bytes()).hexdigest()
        for f in read(self.base/'q2_sorties.csv').itertuples():
            m=specs[f.sortie_id];shape={k:m[k] for k in ['uav_type','box_ids','service_sequence','boxes_by_service','relative_takeoff_time','relative_delivery_times','relative_return_time']}
            signature=hashlib.sha256(json.dumps(dict(shape=shape,geometry=geometry_hash,code=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),radio=hashlib.sha256((ROOT/'src/q3/terrain_los.py').read_bytes()).hexdigest()),sort_keys=True).encode()).hexdigest()
            file=cache_root/(signature+'.json');hit=file.exists()
            if hit:cached=json.loads(file.read_text())
            else:
                ff=frame[frame.task_id==f.sortie_id].copy();ff.time-=f.preparation_start_s;tr=SortieTrajectory(ff,self.pid,f.sortie_id);cache={}
                lo=f.takeoff_s-f.preparation_start_s;hi=f.return_s-f.preparation_start_s
                def at(t):
                    if t not in cache:
                        xyz=tr.position([t])[0];ll=TF.transform(*xyz[:2]);blocked=blocked_line_cells(self.dem,*ll,xyz[2],*self.gll);cache[t]=(float(self.lm['transport<->G01']-fspl_db(self.pc.f_mhz,np.linalg.norm(xyz-self.gateway))-self.pc.l_obs_db*blocked),bool(blocked))
                    return cache[t]
                times=tr.sample_times(lo,hi,.5);pending=[]
                for a,b in zip(times[:-1],times[1:]):
                    va=at(float(a));vb=at(float(b))
                    if va[1]!=vb[1] or (va[0]>=0)!=(vb[0]>=0):pending.append((float(a),float(b)))
                while pending:
                    a,b=pending.pop()
                    if b-a<=.05:continue
                    mid=(a+b)/2;at(mid)
                    for x,y in [(a,mid),(mid,b)]:
                        vx=at(x);vy=at(y)
                        if vx[1]!=vy[1] or (vx[0]>=0)!=(vy[0]>=0):pending.append((x,y))
                ts=sorted(cache);intervals=[];begin=None
                for i,t in enumerate(ts):
                    low=cache[t][0]<0
                    if low and begin is None:begin=i
                    if begin is not None and (not low or i==len(ts)-1):
                        a=max(lo,ts[max(0,begin-1)]-2);b=min(hi,t+2)
                        if intervals and a<=intervals[-1][1]:intervals[-1][1]=max(b,intervals[-1][1])
                        else:intervals.append([a,b])
                        begin=None
                cached=dict(signature=signature,shape=shape,geometry=geometry_hash,intervals=intervals,samples=len(cache),step_s=.5,boundary_s=.05,guard_s=2.);write(file,cached)
            for j,(a,b) in enumerate(cached['intervals']):
                aid=f'{self.pid}_{f.sortie_id}_G{j:02d}';a+=f.preparation_start_s;b+=f.preparation_start_s
                rows.append(dict(atomic_task_id=aid,parent_gap_id=aid,pareto_id=self.pid,transport_sortie_id=f.sortie_id,service_start_s=a,service_end_s=b,service_duration_s=b-a,Gamma_C_db=0.,construction_guard_s=2.))
            log.append(dict(sortie_id=f.sortie_id,signature=signature,cache_hit=hit,intervals=len(cached['intervals'])));print('TEMPLATE',self.pid,f.sortie_id,hit,flush=True)
        write_csv(self.dest/'guarded_atomic_tasks.csv',rows);write(self.dest/'template_log.json',log);return pd.DataFrame(rows)

from pathlib import Path
original_export=previous.export
def export_new(e,result,ident):
    original_export(e,result,ident);dest=e.dest/'solutions'/ident;p=dest/f'joint_metrics_{e.pid}.json';m=json.loads(p.read_text());m.pop('external_structure_provenance',None);m.update(geometry_version=VERSION,result_line='OWN_GENERATED' if e.pid.startswith('A') else 'EXTERNAL_CONTROL',source_provenance='results/reset/pattern_pool.json' if e.pid.startswith('A') else 'results/xb1/source/manifest.json');write(p,m)
    p=dest/'input_manifest.json';manifest=json.loads(p.read_text())
    for f in DATA.glob('*'):
        if f.is_file():manifest['hashes'][str(f.relative_to(ROOT))]=hashlib.sha256(f.read_bytes()).hexdigest()
    manifest['hashes'][str(Path(__file__).relative_to(ROOT))]=hashlib.sha256(Path(__file__).read_bytes()).hexdigest();write(p,manifest)

def configure():
    core.RESULTS_Q2=OUT/'q2';shift.RESULTS_Q2=OUT/'q2';exporter.RESULTS_Q2=OUT/'q2'
    previous.XBEngine=ResetEngine;previous.OUT=OUT/'q3';previous.export=export_new

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('pid');args=p.parse_args();configure();previous.run(args.pid)
