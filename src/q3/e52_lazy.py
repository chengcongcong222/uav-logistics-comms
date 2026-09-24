"""Checkpointed feasibility-first relay rescue, independent of legacy E5 writers.

Run: python -m src.q3.e52_lazy [--max-atoms N] [--resume]
Canonical E52 tables are produced only after search and merge-back finish.
READY is issued separately by the independent validator, never by this solver.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import time

import numpy as np
import pandas as pd

from src.common.paths import PROCESSED_DIR, RESULTS_Q2, RESULTS_DIR, DEM_TIF
from src.common.terrain import Dem
from src.q3.e52_geometry import SortieTrajectory, diameter_infeasible, partition_interval, safe_bbox
from src.q3.link_budget import load_comm_params, pair_lmax, max_range_m, fspl_db
from src.q3.relay_candidate_generator import TF
from src.q3.relay_geometry import evaluate_relay_site, load_relay_params, o01_pos
from src.q3.terrain_los import blocked_line_cells

Q3 = RESULTS_DIR / 'q3'
OUT = Q3 / 'e52_rescue'
CONFIG = dict(generation_mode='LAZY_FEASIBILITY_FIRST', candidate_set_complete=False,
              step_s=0.5, boundary_tolerance_s=0.1, initial_partition_s=30.0,
              min_atomic_s=2.0, max_split_depth=10, soft_budget_s=30.0,
              hard_budget_s=120.0, preferred_candidates=3, workers=1, seed=20260924,
              grid_xy_m=[120, 60, 30], grid_agl_m=list(range(25, 301, 25)))


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    temp.replace(path)


def write_csv(path, rows, columns=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    pd.DataFrame(rows, columns=columns).to_csv(temp, index=False)
    temp.replace(path)


def fingerprint():
    root = Path(__file__).resolve().parents[2]
    inputs = list((root / 'src/q3').glob('e52_*.py'))
    inputs += [root / 'src/q3/terrain_los.py', root / 'src/q3/relay_geometry.py',
               root / 'src/common/terrain.py', root / 'src/q3/link_budget.py',
               root / 'src/q3/relay_candidate_generator.py',
               root / 'src/common/paths.py', root / 'src/common/schemas.py',
               root / 'src/common/transport_energy.py',
               root / 'environment/raw_manifest_sha256.txt', DEM_TIF]
    inputs += [PROCESSED_DIR / n for n in ['nodes.csv', 'relay_uav_types.csv', 'communication_parameters.json', 'dem_metadata.json']]
    inputs += [Q3 / 'relay_sites.csv', Q3 / 'relay_task_candidates.csv', Q3 / 'relay_unresolved.csv']
    for pid in ['P01', 'P02', 'P03']:
        inputs += [Q3 / f'direct_gaps_{pid}.csv', RESULTS_Q2 / 'pareto_schedules' / pid / 'transport_trace.csv']
    hashes = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}
    value = json.dumps({'config': CONFIG, 'files': hashes}, sort_keys=True).encode()
    return hashlib.sha256(value).hexdigest(), hashes


class Engine:
    def __init__(self):
        self.dem = Dem()
        self.pc, _ = load_comm_params()
        self.pr, self.lm = load_relay_params(), pair_lmax()
        self.origin = np.array(o01_pos())
        raw = json.loads((PROCESSED_DIR / 'communication_parameters.json').read_text())
        hg = float(raw['endpoints']['固定网关 G01']['天线离地高度（m）']['value'])
        self.gateway = self.origin + [0, 0, hg]
        self.gll = (*TF.transform(*self.gateway[:2]), self.gateway[2])
        self.dtr = max_range_m(self.lm['transport<->relay'], self.pc, False)
        self.drg = max_range_m(self.lm['relay<->G01'], self.pc, False)
        self.sites, self.access_cache, self.position_cache = {}, {}, {}
        self.stats = Counter()
        self.old_ids = {}
        self.trajectories = {}
        for pid in ['P01', 'P02', 'P03']:
            frame = pd.read_csv(RESULTS_Q2 / 'pareto_schedules' / pid / 'transport_trace.csv')
            for sid in frame.task_id.unique():
                self.trajectories[pid, sid] = SortieTrajectory(frame, pid, sid)
        for r in pd.read_csv(Q3 / 'relay_sites.csv').itertuples():
            site = self.add_site(r.x_m, r.y_m, r.agl_m)
            if site:
                self.old_ids[r.site_id] = site['site_id']

    def add_site(self, x, y, agl):
        if not 0 < agl <= self.pr['max_agl_m']:
            return None
        key = '|'.join(float(v).hex() for v in [x, y, agl])
        sid = 'E52_' + hashlib.sha256(key.encode()).hexdigest()[:24]
        if sid in self.sites:
            return self.sites[sid]
        lon, lat = TF.transform(x, y)
        try:
            ground = self.dem.sample(lon, lat)
        except ValueError:
            self.stats['outside_dem'] += 1
            return None
        s = dict(site_id=sid, x_m=float(x), y_m=float(y), agl_m=float(agl),
                 lon=lon, lat=lat, ground_elevation_m=ground, z_amsl_m=ground + agl)
        self.sites[sid] = s
        return s

    def backhaul(self, site):
        if 'backhaul_margin_db' in site:
            self.stats['rg_cache_hits'] += 1
            return site['backhaul_margin_db']
        xyz = np.array([site['x_m'], site['y_m'], site['z_amsl_m']])
        d = float(np.linalg.norm(xyz - self.gateway))
        blocked = blocked_line_cells(self.dem, site['lon'], site['lat'], site['z_amsl_m'], *self.gll)
        self.stats['rg_los_calls'] += 1
        site.update(backhaul_distance_m=d, backhaul_los=not blocked,
                    backhaul_margin_db=self.lm['relay<->G01'] - fspl_db(self.pc.f_mhz, d) - self.pc.l_obs_db * blocked)
        return site['backhaul_margin_db']

    def energy(self, site, duration):
        if 'static_energy' not in site:
            site['static_energy'] = evaluate_relay_site(
                self.dem, self.pr, (site['x_m'], site['y_m'], site['z_amsl_m']),
                (site['lon'], site['lat'], site['z_amsl_m']), self.pr['setup_time_s'], 0)
            self.stats['static_geometry_computations'] += 1
        else:
            self.stats['static_geometry_cache_hits'] += 1
        en = dict(site['static_energy'])
        en['service_energy_kwh'] = (self.pr['hover_power_kw'] + self.pr['comm_power_kw']) * duration / 3600
        en['total_energy_kwh'] = en['flight_energy_kwh'] + en['setup_energy_kwh'] + en['service_energy_kwh']
        en['energy_margin_kwh'] = (1 - self.pr['rho']) * self.pr['energy_kwh'] - en['total_energy_kwh']
        en['return_soc'] = 1 - en['total_energy_kwh'] / self.pr['energy_kwh']
        return en

    def access(self, traj, site, t):
        # Exact float identity, with plan/sortie identity. No rounded-time aliases.
        pkey = (*traj.key, float(t).hex())
        key = (site['site_id'], pkey)
        if key in self.access_cache:
            self.stats['access_cache_hits'] += 1
            return self.access_cache[key]
        if pkey not in self.position_cache:
            xyz = traj.position([t])[0]
            self.position_cache[pkey] = (xyz, TF.transform(*xyz[:2]))
        xyz, ll = self.position_cache[pkey]
        blocked = blocked_line_cells(self.dem, *ll, xyz[2], site['lon'], site['lat'], site['z_amsl_m'])
        d = float(np.linalg.norm(xyz - [site['x_m'], site['y_m'], site['z_amsl_m']]))
        margin = self.lm['transport<->relay'] - fspl_db(self.pc.f_mhz, d) - self.pc.l_obs_db * blocked
        self.stats['access_los_calls'] += 1
        self.access_cache[key] = (margin, bool(blocked))
        return self.access_cache[key]

    def exact(self, traj, site, a, b):
        self.stats['exact_interval_checks'] += 1
        ts = traj.sample_times(a, b, CONFIG['step_s'])
        self.stats['exact_base_sample_requests'] += len(ts)
        minimum, previous = float('inf'), None
        refinement = []
        for t in ts:
            value = self.access(traj, site, t)
            minimum = min(minimum, value[0])
            if value[0] < 0:
                return None
            if previous and previous[1][1] != value[1]:
                refinement.append((previous[0], previous[1], float(t), value))
            previous = (float(t), value)
        while refinement:
            left, lv, right, rv = refinement.pop()
            if right - left <= CONFIG['boundary_tolerance_s']:
                continue
            mid = (left + right) / 2
            mv = self.access(traj, site, mid)
            self.stats['boundary_refinement_samples'] += 1
            minimum = min(minimum, mv[0])
            if mv[0] < 0:
                return None
            if lv[1] != mv[1]:
                refinement.append((left, lv, mid, mv))
            if mv[1] != rv[1]:
                refinement.append((mid, mv, right, rv))
        return minimum

    def check(self, traj, sid, a, b):
        site = self.sites[sid]
        if self.backhaul(site) < 0:
            return None
        self.stats['sparse_interval_checks'] += 1
        # Include vertices in sparse checks so even the cheap stage respects turns.
        sparse = np.unique(np.r_[np.linspace(a, b, 5), traj.vertices(a, b)])
        for t in sparse:
            if self.access(traj, site, t)[0] < 0:
                return None
        en = self.energy(site, b - a)
        if en['energy_margin_kwh'] < 0:
            return None
        margin = self.exact(traj, site, a, b)
        if margin is None:
            return None
        ready = self.pr['prep_time_s'] + en['outbound_time_s'] + self.pr['setup_time_s']
        return dict(site_id=sid, min_access_margin_db=margin,
                    backhaul_margin_db=site['backhaul_margin_db'],
                    min_twohop_margin_db=min(margin, site['backhaul_margin_db']),
                    **en, setup_time_s=self.pr['setup_time_s'], earliest_ready_s=ready,
                    required_transport_shift_s=max(0.0, ready-a), as_is_timing_feasible=int(ready <= a))

    def cheap(self, traj, ids, a, b):
        """Vectorized exact distance necessity over piecewise-linear phase vertices."""
        points = traj.position(traj.vertices(a, b))
        sites = np.array([[self.sites[s][k] for k in ['x_m', 'y_m', 'z_amsl_m']] for s in ids])
        if not len(sites):
            return []
        self.stats['cheap_candidates_examined'] += len(sites)
        dtr = np.linalg.norm(sites[:, None, :] - points[None, :, :], axis=2).max(axis=1)
        drg = np.linalg.norm(sites - self.gateway, axis=1)
        mask = (dtr <= self.dtr) & (drg <= self.drg)
        indices = np.flatnonzero(mask)
        self.stats['after_distance_candidates'] += len(indices)
        # Deterministic promising-first order, not a claim of full enumeration.
        indices = indices[np.argsort(dtr[indices], kind='stable')]
        return [ids[i] for i in indices]

    def search(self, job, warm_ids=()):
        started = time.monotonic()
        traj = self.trajectories[job['pareto_id'], job['transport_sortie_id']]
        a, b = job['start_s'], job['end_s']
        points = traj.position(traj.vertices(a, b))
        bbox = safe_bbox(points, self.dtr, self.drg, self.gateway)
        if bbox is None or diameter_infeasible(points, self.dtr):
            return [], 'COMMON_NECESSARY_REGION_EMPTY' if bbox is None else 'PAIRWISE_DIAMETER_INFEASIBLE', bbox
        examined = set()
        budget = CONFIG['soft_budget_s'] if b-a > CONFIG['min_atomic_s'] else CONFIG['hard_budget_s']

        def try_ids(ids, source, limit=1):
            found = []
            for sid in self.cheap(traj, list(dict.fromkeys(ids)), a, b):
                if sid in examined:
                    continue
                examined.add(sid)
                c = self.check(traj, sid, a, b)
                if c:
                    c['candidate_source'] = source
                    found.append(c)
                    if len(found) >= limit:
                        break
                if time.monotonic() - started > budget:
                    break
            return found

        if warm_ids:
            found = try_ids(warm_ids, 'E5_REVALIDATED', 3)
            if found:
                return found, 'E5_REVALIDATED', bbox
        found = try_ids(list(self.sites), 'E52_EXISTING_SITE')
        if found:
            return found, 'E52_EXISTING_SITE', bbox
        # Soft budget triggers subdivision for long intervals; <=2 s gets hard budget.
        xlo, xhi, ylo, yhi = bbox
        center = points.mean(axis=0)
        for step in CONFIG['grid_xy_m']:
            xs = np.arange(math.ceil(xlo/step), math.floor(xhi/step)+1) * step
            ys = np.arange(math.ceil(ylo/step), math.floor(yhi/step)+1) * step
            xx, yy = np.meshgrid(xs, ys)
            xy = np.column_stack([xx.ravel(), yy.ravel()])
            xy = xy[np.argsort(np.sum((xy-center[:2])**2, axis=1), kind='stable')]
            for heights in [[300,250,200,150,100,50], [275,225,175,125,75,25]]:
                for first in range(0, len(xy), 32):
                    if time.monotonic() - started > budget:
                        return [], 'SEARCH_BUDGET_EXHAUSTED_NOT_INFEASIBLE', bbox
                    ids = []
                    for x, y in xy[first:first+32]:
                        for agl in heights:
                            s = self.add_site(float(x), float(y), float(agl))
                            if s:
                                ids.append(s['site_id'])
                    found = try_ids(ids, f'E52_NEW_GRID_{step}M')
                    if found:
                        return found, 'E52_NEW_GRID', bbox
        if b-a <= CONFIG['min_atomic_s']:
            # Local fine rescue only, seeded by geometrically nearby known sites.
            ranked = self.cheap(traj, list(self.sites), a, b)[:3]
            for sid in ranked:
                seed = self.sites[sid]
                for dx in range(-60,61,5):
                    for dy in range(-60,61,5):
                        if time.monotonic()-started > CONFIG['hard_budget_s']:
                            return [], 'FINE_SEARCH_BUDGET_EXHAUSTED', bbox
                        ids=[]
                        for agl in range(300,0,-5):
                            s=self.add_site(seed['x_m']+dx,seed['y_m']+dy,float(agl))
                            if s:
                                ids.append(s['site_id'])
                        found=try_ids(ids,'E52_FINE_GRID')
                        if found:
                            return found,'E52_FINE_GRID',bbox
            return [], 'CONTINUOUS_RESCUE_REQUIRED', bbox
        return [], 'GRID_SEARCH_EXHAUSTED', bbox


def initial_jobs(engine):
    candidates = pd.read_csv(Q3 / 'relay_task_candidates.csv')
    unresolved = pd.read_csv(Q3 / 'relay_unresolved.csv')
    jobs = []
    for pid in ['P01', 'P02', 'P03']:
        gaps = pd.read_csv(Q3 / f'direct_gaps_{pid}.csv')
        for gi, gap in enumerate(gaps.itertuples()):
            parent = f'{pid}_G{gi:03d}'
            base = dict(pareto_id=pid, parent_gap_id=parent, transport_sortie_id=gap.sortie_id, depth=0)
            rows=[]
            for aid, group in candidates[candidates.parent_gap_id == parent].groupby('atomic_task_id'):
                first=group.iloc[0]
                picks=[group.loc[group.min_twohop_margin_db.idxmax()].site_id,
                       group.loc[group.total_energy_kwh.idxmin()].site_id]
                ids=[engine.old_ids[s] for s in dict.fromkeys(picks)]
                xyz=lambda sid: np.array([engine.sites[sid][k] for k in ['x_m','y_m','z_amsl_m']])
                others=[s for s in group.site_id if s not in picks]
                if others:
                    farthest=max(others,key=lambda s:min(np.linalg.norm(xyz(engine.old_ids[s])-xyz(k)) for k in ids))
                    ids.append(engine.old_ids[farthest])
                rows.append(dict(base, old_atomic_task_id=aid, start_s=float(first.service_start_s),
                                 end_s=float(first.service_end_s), warm_ids=ids, origin='OLD_RESOLVED'))
            for r in unresolved[unresolved.atomic_task_id.str.startswith(parent+'_')].itertuples():
                traj=engine.trajectories[pid,gap.sortie_id]
                for a,b in partition_interval(traj,float(r.start_s),float(r.end_s)):
                    rows.append(dict(base,old_atomic_task_id=r.atomic_task_id,start_s=a,end_s=b,
                                     warm_ids=[],origin='OLD_UNRESOLVED'))
            rows.sort(key=lambda j:j['start_s'])
            cursor=float(gap.start_s)
            for r in rows:
                if abs(r['start_s']-cursor)>1e-6 or r['end_s']<=r['start_s']:
                    raise ValueError(f'Invalid warm partition {parent}')
                cursor=r['end_s']
            if abs(cursor-float(gap.end_s))>1e-6:
                raise ValueError(f'Missing warm parent coverage {parent}')
            jobs.extend(rows)
    return jobs


def snapshot(engine, state):
    state['stats']=dict(engine.stats)
    # Search caches are reproducible; static site/energy cache persists across resume.
    state['sites']=engine.sites
    write_json(OUT/'checkpoint.json',state)
    flat=[]
    for task in state['resolved']:
        flat.append({k:v for k,v in task.items() if k not in ['candidates','warm_ids']})
    write_csv(OUT/'resolved_atoms.csv',flat)
    write_csv(OUT/'candidate_sites.csv',[{k:v for k,v in s.items() if k!='static_energy'} for s in engine.sites.values()])


def merge_parent(engine, tasks):
    """Greedy fixed point over adjacent tasks using only their candidate union."""
    tasks=sorted(tasks,key=lambda t:t['start_s'])
    index=0
    while index+1<len(tasks):
        left,right=tasks[index:index+2]
        traj=engine.trajectories[left['pareto_id'],left['transport_sortie_id']]
        ids=list(dict.fromkeys(c['site_id'] for t in [left,right] for c in t['candidates']))
        found=[]
        for sid in ids:
            c=engine.check(traj,sid,left['start_s'],right['end_s'])
            if c:
                c['candidate_source']='E52_MERGE_BACK'
                found.append(c)
                if len(found)==3:
                    break
        if found:
            merged=dict(left,end_s=right['end_s'],candidates=found,source='E52_MERGE_BACK')
            merged['merged_from']=left.get('merged_from',[left['old_atomic_task_id']])+right.get('merged_from',[right['old_atomic_task_id']])
            tasks[index:index+2]=[merged]
            engine.stats['merge_back_operations']+=1
            index=max(0,index-1)
        else:
            index+=1
    return tasks


def export(engine,state):
    atoms,pairs,used=[],[],set()
    counts=Counter()
    for t in sorted(state['resolved'],key=lambda t:(t['parent_gap_id'],t['start_s'])):
        parent=t['parent_gap_id']; ai=counts[parent]; counts[parent]+=1
        aid=f'{parent}_E52_A{ai:03d}'
        base=dict(atomic_task_id=aid,parent_gap_id=parent,pareto_id=t['pareto_id'],
                  transport_sortie_id=t['transport_sortie_id'],service_start_s=t['start_s'],
                  service_end_s=t['end_s'],service_duration_s=t['end_s']-t['start_s'])
        atoms.append(dict(base,candidate_count=len(t['candidates']),source=t['source'],
                          candidate_set_complete=False,generation_mode=CONFIG['generation_mode']))
        for c in t['candidates']:
            pairs.append(dict(base,**c)); used.add(c['site_id'])
    sites=[{k:v for k,v in engine.sites[s].items() if k!='static_energy'} for s in sorted(used)]
    write_csv(Q3/'relay_atomic_tasks_e52.csv',atoms)
    write_csv(Q3/'relay_task_candidates_e52.csv',pairs)
    write_csv(Q3/'relay_sites_e52.csv',sites)
    write_csv(Q3/'relay_unresolved_e52.csv',state['unresolved'],
              columns=['pareto_id','parent_gap_id','transport_sortie_id','start_s','end_s','reason'])
    summary=[]
    for pid in ['P01','P02','P03']:
        aa=[t for t in atoms if t['pareto_id']==pid]; cc=[c for c in pairs if c['pareto_id']==pid]
        bytask={t['atomic_task_id']:[c for c in cc if c['atomic_task_id']==t['atomic_task_id']] for t in aa}
        shifts=[min(c['required_transport_shift_s'] for c in rows) for rows in bytask.values()]
        summary.append(dict(pareto_id=pid,parent_gaps=len(pd.read_csv(Q3/f'direct_gaps_{pid}.csv')),
                            atomic_tasks=len(aa),candidate_pairs=len(cc),sites=len({c['site_id'] for c in cc}),
                            candidate_count_min=min((t['candidate_count'] for t in aa),default=0),
                            candidate_count_max=max((t['candidate_count'] for t in aa),default=0),
                            zero_shift_tasks=sum(s<=1e-9 for s in shifts),
                            max_required_shift_s=max(shifts,default=0),
                            separate_mission_min_energy_sum_kwh=sum(min(c['total_energy_kwh'] for c in rows) for rows in bytask.values())))
    meta=dict(config=CONFIG,fingerprint=state['fingerprint'],input_hashes=state['input_hashes'],
              search_status='E52_FEASIBILITY_RESOLVED' if not state['unresolved'] else 'E52_FEASIBILITY_BLOCKED',
              gate='PENDING_INDEPENDENT_VALIDATION',summary=summary,stats=dict(engine.stats),
              runtime_s=state['runtime_s'],unresolved=len(state['unresolved']),
              old_unresolved_atoms=8,old_unresolved_distinct_parent_gaps=5,
              search_outcomes=dict(Counter(e['result'] for e in state['events'])),
              validation_semantics='Numerical whole-interval check: <=0.5s, all phase/end boundaries, LOS transitions refined <=0.1s; not an analytic continuous-time certificate',
              energy_sum_semantics='Sum of per-atom minimum retained-candidate separate-sortie energies; not a proven lower bound on later merged schedules',
              old_exhaustive_los_call_count=None,old_exhaustive_runtime_s=None)
    write_json(Q3/'e52_run_meta.json',meta)
    write_json(OUT/'progress_events.json',state['events'])
    print(json.dumps(meta,ensure_ascii=False,indent=2),flush=True)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--resume',action='store_true')
    parser.add_argument('--max-atoms',type=int,default=0,help='Controlled interruption for checkpoint validation')
    args=parser.parse_args()
    signature,hashes=fingerprint()
    engine=Engine(); started=time.monotonic()
    checkpoint=OUT/'checkpoint.json'
    if checkpoint.exists():
        if not args.resume:
            raise SystemExit('Checkpoint exists. Use --resume; preserve prior run explicitly before restarting.')
        state=json.loads(checkpoint.read_text())
        if state['fingerprint']!=signature:
            raise SystemExit('Checkpoint input/code/config fingerprint mismatch; refuse stale resume.')
        engine.sites.update(state['sites']);engine.stats.update(state['stats'])
    else:
        state=dict(fingerprint=signature,input_hashes=hashes,pending=initial_jobs(engine),resolved=[],
                   unresolved=[],events=[],merged_parents=[],runtime_s=0.0,stage='SEARCH')
    old_runtime=state['runtime_s'];done=0
    while state['pending']:
        job=state['pending'][0]; tick=time.monotonic(); before=engine.stats.copy()
        cands,source,bbox=engine.search(job,job.get('warm_ids',[]))
        a,b=job['start_s'],job['end_s']
        if cands:
            state['resolved'].append(dict(job,candidates=cands,source=source))
        elif b-a>CONFIG['min_atomic_s'] and job['depth']<CONFIG['max_split_depth']:
            traj=engine.trajectories[job['pareto_id'],job['transport_sortie_id']]
            pieces=partition_interval(traj,a,b) if b-a>30 else [(a,(a+b)/2),((a+b)/2,b)]
            children=[dict(job,start_s=x,end_s=y,depth=job['depth']+1,warm_ids=[]) for x,y in pieces]
            state['pending'][1:1]=children
            source='SPLIT_AFTER_'+source
        else:
            state['unresolved'].append(dict(job,reason=source))
        state['pending'].pop(0)
        delta=engine.stats-before
        event=dict(pareto_id=job['pareto_id'],parent_gap_id=job['parent_gap_id'],
                   old_atomic_task_id=job['old_atomic_task_id'],origin=job['origin'],
                   start_s=a,end_s=b,duration_s=b-a,split_depth=job['depth'],
                   result=source,candidates=len(cands),runtime_s=time.monotonic()-tick,
                   retained_site_ids=[c['site_id'] for c in cands],
                   min_retained_margin_db=min((c['min_twohop_margin_db'] for c in cands),default=None),
                   bbox=bbox,counts=dict(delta),remaining=len(state['pending']))
        state['events'].append(event);state['runtime_s']=old_runtime+time.monotonic()-started
        snapshot(engine,state)
        print(json.dumps(event,ensure_ascii=False),flush=True)
        done+=1
        if args.max_atoms and done>=args.max_atoms:
            print('E52_CHECKPOINT_SAVED_CONTROLLED_STOP',flush=True);return
    state['stage']='MERGE_BACK'
    for parent in sorted({t['parent_gap_id'] for t in state['resolved']}):
        if parent in state['merged_parents']:
            continue
        tasks=[t for t in state['resolved'] if t['parent_gap_id']==parent]
        # Never merge across unresolved holes.
        if not any(t['parent_gap_id']==parent for t in state['unresolved']):
            merged=merge_parent(engine,tasks)
            state['resolved']=[t for t in state['resolved'] if t['parent_gap_id']!=parent]+merged
            print(f'merge-back {parent}: {len(tasks)} -> {len(merged)}',flush=True)
        state['merged_parents'].append(parent)
        state['runtime_s']=old_runtime+time.monotonic()-started
        snapshot(engine,state)
    state['stage']='SEARCH_COMPLETE';state['runtime_s']=old_runtime+time.monotonic()-started
    snapshot(engine,state);export(engine,state)


if __name__=='__main__':
    main()
