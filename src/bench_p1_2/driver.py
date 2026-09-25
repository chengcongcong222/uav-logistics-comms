"""Five-anchor DIAGNOSTIC_WARM admission; never a cold benchmark entry point.

Finite internal structure portfolio, fresh run-local radio tasks/edges, bounded
continuous timing and relay regrouping. No performance/proof claims.
"""
import argparse, copy, itertools, json, random, shutil, sys, time, warnings
from pathlib import Path
import numpy as np
from scipy.optimize import linprog
from src.bench_p1.common import ROOT, write, append, digest, signature
from src.bench_p1 import q3_adapter as adapter
from src.reset.cell_challenge import Cell
from src.q3.e7_core import sequences_for

OUT = ROOT / 'results/p1_2'
AXES = ('J_norm', 'joint_makespan_s', 'total_energy_kwh', 'transport_sorties', 'relay_sorties')
SEEDS = (26092511, 26092512)
SOURCES = [('A11','A11_Q3_001'), ('A11','A11_Q3_002'),
           ('A11','A11_Q3_004_CC'), ('AN01','AN01_Q3_001_CC'), ('A03','A03_Q3_001')]

def audit(root, pid, package):
    sys.path.insert(0, str(ROOT / 'validation/mathematical'))
    import reset_q3_validate as q3
    q3.OUT=root; q3.audit.IndependentAudit=q3.Checker
    q3.audit.Q3=root/'q3'; q3.audit.DATA=ROOT/'results/reset/geometry'; q3.audit.OUT=package
    result=q3.audit.validate_plan(pid,.5)
    write(package/'validation_0.5.json',dict(result,status='P1_Q3_INDEPENDENTLY_VALIDATED'))
    return result

def admit_portfolio():
    first=json.loads((OUT/'warm_seed_readmission.json').read_text())
    assert first['status']=='READMITTED', 'A11 must pass before portfolio work'
    root=OUT/'warm_readmission'; records=[]
    for pid,ident in SOURCES:
        src=ROOT/'results/reset/q3'/pid/'solutions'/ident
        dest=root/'q3'/pid/'solutions'/ident
        if ident!='A11_Q3_001':
            if dest.exists():raise RuntimeError('Refuse overwrite '+str(dest))
            base=root/'q2/pareto_schedules'/pid
            if not base.exists():shutil.copytree(ROOT/'results/reset/q2/pareto_schedules'/pid,base)
            shutil.copytree(src,dest)
            result=audit(root,pid,dest)
        else:result=first['audit']
        witness=json.loads((dest/'witness.json').read_text())
        assert result['hard_violations']==0 and result['uncovered_sample_count']==0
        records.append(dict(pid=pid,ident=ident,package=str(dest.relative_to(ROOT)),
                            metrics=witness['metrics'],source='AUTONOMOUS_INTERNAL_G2',
                            hashes={p.name:digest(p) for p in dest.iterdir() if p.is_file()}))
        write(OUT/'warm_portfolio_readmission.json',records)
        print('READMITTED',ident,flush=True)

class Anchor:
    def __init__(self,axis,root):
        assert axis in AXES
        self.axis=axis;self.ident='ANCHOR_'+axis;self.root=root
        self.weight=[float(k==axis) for k in AXES]
        self.scales=[1.,16000.,120.,80.,20.]
    def event(self,action,**kwargs):
        append(self.root/'anchor_trace.jsonl',dict(mode='DIAGNOSTIC_WARM',anchor=self.axis,
               action=action,cpu_s=time.process_time(),**kwargs))
    def key(self,m):
        late=float(m['J_late'])
        return (int(late>1e-4),late if late>1e-4 else 0.,float(m[self.axis]))
    def rank(self,rows,stage):
        ranked=sorted(rows,key=lambda r:(self.key(r['metrics']),r['id']))
        self.event(stage,candidates=[dict(id=r['id'],pid=r['pid'],key=self.key(r['metrics']),
                   metrics=r['metrics']) for r in ranked],selected=ranked[0]['id'])
        return ranked

def resource_orders(model,answer):
    """Keep the warm feasible machine order, optimize all continuous times."""
    cuts=[]
    for kind,typ,specs,allowed in model.resource_specs:
        key='uav_id' if kind=='UAV' else 'battery_id'
        for resource in allowed:
            jobs=[s for s in specs if answer['assignments'][model.ids[s[0]]][key]==resource]
            jobs.sort(key=lambda s:answer['shifts'][model.ids[s[0]]]+s[1])
            cuts += [(a[0],b[0],float(a[2]-b[1])) for a,b in zip(jobs[:-1],jobs[1:])]
    return cuts

def limited_lp(*args,**kwargs):
    kwargs['options']=dict(threads=1,time_limit=3.)
    return linprog(*args,**kwargs)

def remap_sites(e,witness,old_sites):
    """IDs are serialization hashes, not physics; match unique frozen coords."""
    mapping={}
    for old in old_sites:
        matches=[sid for sid,s in e.sites.items()
                 if max(abs(float(old[k])-float(s[k])) for k in ('x_m','y_m','agl_m'))<=1e-7]
        if len(matches)!=1:raise ValueError('Missing/ambiguous frozen coordinate '+old['site_id'])
        mapping[old['site_id']]=matches[0]
    result=copy.deepcopy(witness)
    for row in result['groups']+result['selected']:row['site_id']=mapping[row['site_id']]
    return result,mapping

def optimize(e,witness,pref,exact=True,groups=None):
    if exact:
        model=Cell(e,e.pid,witness,'timeliness')
        seq=witness['sequences']
    else:
        model=adapter.core.Timing(e,e.pid,groups,late_budget=1e-4 if witness['metrics']['J_late']<=1e-4 else None)
        # Deterministic two-machine list order from current communication times.
        ends=[0.,0.];seq=[[],[]]
        spans=[]
        for j,g in enumerate(groups):
            a=min(float(e.atoms.loc[t].service_start_s)+witness['shifts'][e.atoms.loc[t].transport_sortie_id] for t in g['task_ids'])
            b=max(float(e.atoms.loc[t].service_end_s)+witness['shifts'][e.atoms.loc[t].transport_sortie_id] for t in g['task_ids'])
            spans.append((a,j,b))
        for a,j,b in sorted(spans):
            r=min(range(2),key=lambda r:ends[r]);seq[r].append(j);ends[r]=max(ends[r],a-model.leads[j])+b-a+model.leads[j]+model.tails[j]
    cuts=resource_orders(model,witness)
    value=adapter.preference_lp(model,seq,cuts,pref,limited_lp,exact=exact)
    result=model.materialize(value[0],seq,cuts) if value is not None else None
    pref.event('joint_adjustment',pid=e.pid,exact_energy=exact,lp_solves=model.lp_solves,
               fixed_transport_sorties=model.n,relay_groups=model.k,found=result is not None,
               domain='FREE_CONTINUOUS_TIMES_FIXED_WARM_TYPED_RESOURCE_ORDERS',
               metrics=result['metrics'] if result else None)
    return result

def relay_options(e,witness,pref):
    """Actual merge/split/site proposals ranked before their timing LP."""
    old=witness['groups'];options=[]
    for i,j in itertools.combinations(range(len(old)),2):
        ids=sorted(set(old[i]['task_ids']+old[j]['task_ids']))
        for site in sorted(e.common(ids)):
            groups=[copy.deepcopy(g) for k,g in enumerate(old) if k not in (i,j)]
            groups.append(dict(site_id=site,task_ids=ids));options.append(('merge',groups))
    for i,g in enumerate(old):
        for site in sorted(e.common(g['task_ids'])):
            if site!=g['site_id']:
                groups=copy.deepcopy(old);groups[i]['site_id']=site;options.append(('site',groups))
        ids=sorted(g['task_ids'],key=lambda t:float(e.atoms.loc[t].service_start_s))
        if len(ids)>1:
            groups=[copy.deepcopy(x) for j,x in enumerate(old) if j!=i]
            groups += [dict(site_id=g['site_id'],task_ids=part) for part in (ids[:len(ids)//2],ids[len(ids)//2:])]
            options.append(('split',groups))
    def score(item):
        move,groups=item;starts=[];ends=[];energy=0.
        for g in groups:
            en=e.energy(e.sites[g['site_id']],0)
            a=min(float(e.atoms.loc[t].service_start_s)+witness['shifts'][e.atoms.loc[t].transport_sortie_id] for t in g['task_ids'])
            b=max(float(e.atoms.loc[t].service_end_s)+witness['shifts'][e.atoms.loc[t].transport_sortie_id] for t in g['task_ids'])
            starts.append(max(0,en['outbound_time_s']+e.pr['prep_time_s']+e.pr['setup_time_s']-a))
            ends.append(b+en['return_time_s']);energy+=en['total_energy_kwh']+(b-a)*e.pr['hover_power_kw']/3600
        proxy={'J_norm':sum(starts),'joint_makespan_s':max(ends),
               'total_energy_kwh':energy,'transport_sorties':len(witness['shifts']), 'relay_sorties':len(groups)}
        return (proxy[pref.axis],sum(starts),len(groups),signature(groups))
    options.sort(key=score)
    pref.event('relay_proposal_selection',pid=e.pid,count=len(options),
               ranking='ANCHOR_SPECIFIC_HEURISTIC_ONLY_NOT_FEASIBLE_METRICS',
               top=[dict(move=m,key=score((m,g)),groups=len(g),signature=signature(g)) for m,g in options[:4]])
    return options[:1]

def run(seed,mode):
    assert mode=='DIAGNOSTIC_WARM' and seed in SEEDS
    root=OUT/'runs'/str(seed)
    if root.exists():raise RuntimeError('Refuse overwrite '+str(root))
    root.mkdir(parents=True);tick=time.process_time();rng=random.Random(seed)
    write(root/'config.json',dict(mode=mode,seed=seed,formal_cold_start_eligible=False,
          anchors=AXES,structures=['A11','AN01','A03'],frozen_sites=118,Gamma_C_db=0,
          max_transport_paths_per_anchor=2,max_relay_neighbors_per_path=1,max_challenges_per_anchor=1,
          solver_call_limit_s=3,global_optimum_proven=False,
          cpu_scope='ALL initialization+private radio+selection+LP+export; independent audits reported separately',
          budget_kind='FIXED_SMALL_REQUEST_COUNTS_NOT_FORMAL_CPU_CALIBRATION'))
    # Record and enforce algorithm-input exclusions; unchanged independent audit
    # has its own legacy initialization, which is outside candidate search.
    auditing=False;logging=False
    def hook(event,args):
        nonlocal logging
        if event in ('subprocess.Popen','os.system','os.fork','os.posix_spawn'):raise RuntimeError('No solver children')
        if event=='open' and isinstance(args[0],(str,bytes)) and not logging:
            name=str(args[0]); logging=True
            try:append(root/'input_opens.jsonl',dict(path=name,auditing=auditing,cpu_s=time.process_time()))
            finally:logging=False
            if 'evaluation_only_' in name or name.endswith('/p1_setup/preferences.json'):raise RuntimeError('Holdout forbidden')
            if not auditing and ('/results/xb1/' in name or '/results/reset/q3/B' in name or '/results/reset/q2/pareto_schedules/B' in name):raise RuntimeError('External solutions forbidden')
            if not auditing and any(x in name for x in ('/results/q3/e52/','/results/q3/e6/','/results/q3/e8/','/pareto_schedules/P01/','/pareto_schedules/P02/','/pareto_schedules/P03/')):raise RuntimeError('Legacy task/edge input forbidden')
    sys.addaudithook(hook)
    records=json.loads((OUT/'warm_portfolio_readmission.json').read_text());archive=[];engines={};audit_cpu=0.
    for pid in ['A11','AN01','A03']:
        base=root/'q2/pareto_schedules'/pid
        shutil.copytree(OUT/'warm_readmission/q2/pareto_schedules'/pid,base)
        e=adapter.Engine(root,pid,lambda phase:print(seed,pid,phase,flush=True));e.pool()
        assert len(e.sites)==118
        assert all(key[0] in (pid,'P01') for key in e.trajectories)
        engines[pid]=e
        for r in [r for r in records if r['pid']==pid]:
            package=ROOT/r['package']
            for name,h in r['hashes'].items():assert digest(package/name)==h
            w=json.loads((package/'witness.json').read_text())
            w,mapping=remap_sites(e,w,adapter.read(package/f'candidate_sites_{pid}.csv').to_dict('records'))
            write(e.dest/(r['ident']+'_site_id_map.json'),dict(mapping=mapping,
                  coordinate_tolerance_m=1e-7,coordinates_replaced=False,
                  rule='USE_UNIQUE_EXISTING_FROZEN_SITE_ID'))
            assert sorted(t for g in w['groups'] for t in g['task_ids'])==sorted(e.atoms.index)
            assert all(g['site_id'] in e.common(g['task_ids']) for g in w['groups'])
            archive.append(dict(id=r['ident'],pid=pid,metrics=w['metrics'],witness=w,verified=True,origin='READMITTED_INTERNAL_WARM'))
    adapter.core.RESULTS_Q2=root/'q2';adapter.shift.RESULTS_Q2=root/'q2';adapter.exporter.RESULTS_Q2=root/'q2'
    serial=0;outcomes=[]
    def save(e,answer,pref,origin):
        nonlocal serial,auditing,audit_cpu
        serial+=1;ident=f'D{seed}_{serial:03d}'
        adapter.export_local(e,copy.deepcopy(answer),ident)
        package=e.dest/'solutions'/ident
        metricfile=package/f'joint_metrics_{e.pid}.json'
        m=json.loads(metricfile.read_text());m.update(mode=mode,source_provenance='INTERNAL_WARM_DIAGNOSTIC',formal_cold_start_eligible=False)
        write(metricfile,m);start=time.process_time();auditing=True
        try:result=audit(root,e.pid,package)
        except Exception as exc:
            write(package/'validation_failure.json',dict(error=repr(exc)))
            pref.event('independent_rejection',id=ident,error=repr(exc));return None
        finally:auditing=False;audit_cpu+=time.process_time()-start
        row=dict(id=ident,pid=e.pid,metrics=answer['metrics'],witness=answer,verified=True,origin=origin)
        archive.append(row)
        pref.event('independently_verified_feedback',id=ident,pid=e.pid,origin=origin,metrics=row['metrics'],
                   structure_hash=digest(e.base/'missions.json'),tasks_hash=digest(e.dest/'guarded_atomic_tasks.csv'),
                   tasks=len(e.atoms),package=str(package.relative_to(ROOT)))
        return row
    for axis in AXES:
        pref=Anchor(axis,root)
        ranked=pref.rank(archive,'transport_retention_and_q3_target_selection')
        # A protected incumbent plus one different structural probe. The probe
        # can be soft-late but can never replace a verified zero-late incumbent.
        first=ranked[0];others=[r for r in archive if r['pid']!=first['pid']]
        rng.shuffle(others)
        other=min(others,key=lambda r:r['metrics'][axis])
        selected=[first,other]
        pref.event('transport_portfolio_expansion',retained=[r['id'] for r in selected],
                   structural_probe_rule='MIN_ACTUAL_Q3_ANCHOR_ON_OTHER_STRUCTURE',
                   uses_transport_count_as_relay_proxy=False)
        successes=[]
        for row in selected:
            e=engines[row['pid']];w=row['witness']
            pref.event('transport_structure_entered',pid=e.pid,source=row['id'],
                       structure_hash=digest(e.base/'missions.json'),task_hash=digest(e.dest/'guarded_atomic_tasks.csv'),tasks=len(e.atoms))
            answer=optimize(e,w,pref)
            if answer:
                result=save(e,answer,pref,'CONTINUOUS_JOINT_ADJUSTMENT')
                if result:successes.append(result['id'])
            for move,groups in relay_options(e,w,pref):
                answer=optimize(e,w,pref,exact=False,groups=groups)
                pref.event('relay_neighbor_attempt',pid=e.pid,move=move,groups=len(groups),found=answer is not None)
                if answer:
                    result=save(e,answer,pref,'RELAY_'+move.upper())
                    if result:successes.append(result['id'])
        feedback=pref.rank(archive,'q3_feedback_archive_update')
        # Feedback actually determines the next model/structure to be solved.
        target=feedback[0];pref.event('challenge_target_selection',id=target['id'],pid=target['pid'],metrics=target['metrics'])
        answer=optimize(engines[target['pid']],target['witness'],pref)
        if answer:
            result=save(engines[target['pid']],answer,pref,'FEEDBACK_SELECTED_CHALLENGE')
            if result:successes.append(result['id'])
        best=pref.rank(archive,'final_anchor_retention')[0]
        assert best['metrics']['J_late']<=1e-4
        outcomes.append(dict(anchor=axis,best_id=best['id'],metrics=best['metrics'],verified_new_paths=successes))
        write(root/'outcomes.json',outcomes)
        print('ANCHOR_DONE',seed,axis,len(successes),flush=True)
    write(root/'archive.json',[{k:v for k,v in r.items() if k!='witness'} for r in archive])
    write(root/'timing.json',dict(total_cpu_s=time.process_time()-tick,audit_cpu_s=audit_cpu,
          search_export_cpu_s=time.process_time()-tick-audit_cpu,formal_comparison=False))

def main():
    warnings.filterwarnings('ignore',message='Unrecognized options detected')
    p=argparse.ArgumentParser();p.add_argument('--admit',action='store_true')
    p.add_argument('--mode',choices=['DIAGNOSTIC_WARM']);p.add_argument('--seed',type=int,choices=SEEDS)
    a=p.parse_args()
    if a.admit:admit_portfolio()
    else:run(a.seed,a.mode)

if __name__=='__main__':main()
