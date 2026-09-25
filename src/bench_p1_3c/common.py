"""Isolated P1.3-C inputs and execution validation."""
import copy, json, shutil, time, os
from pathlib import Path
from src.bench_p1.common import ROOT, write, digest, signature
from src.bench_p1 import q3_adapter as adapter
from src.bench_p1_3b.common import install_input_guard
from src.bench_p1_2.driver import audit
from src.q3.e6_resources import sortie_column, color_intervals
from src.q3.e7_core import sequences_for

OUT=ROOT/os.environ.get('P13C_OUTPUT','results/p1_3c')
BASE='f150743dea36d655204e74372580f98ebd9a8cf8'
SEED=26092511

def read(p):return json.loads(Path(p).read_text())

def engine(pid):
    root=OUT/pid;root.mkdir(parents=True,exist_ok=True)
    old=ROOT/'results/p1_3b/screening'/pid
    source=old/'q3'/pid
    target=root/'q2/pareto_schedules'/pid
    if not target.exists():shutil.copytree(old/'q2/pareto_schedules'/pid,target)
    class SavedEngine(adapter.Engine):
        def demands(self,frame):return adapter.read(source/'guarded_atomic_tasks.csv')
    e=SavedEngine(root,pid,lambda stage:print(pid,stage,flush=True))
    for row in adapter.read(source/'candidate_pairs.csv').to_dict('records'):
        assert row['site_id'] in e.sites
        e.edges[pid][row['atomic_task_id']][row['site_id']]=row
    assert len(e.sites)==118
    for f in ['guarded_atomic_tasks.csv','candidate_pairs.csv','candidate_sites.csv']:
        shutil.copyfile(source/f,e.dest/f)
    write(root/'input_reuse.json',dict(base_commit=BASE,source='Same structure own P1.3-B cold tasks/edges; time translation invariant link geometry',
        hashes={str(f.relative_to(ROOT)):digest(f) for f in [*target.glob('*'),*(source/n for n in ['guarded_atomic_tasks.csv','candidate_pairs.csv','candidate_sites.csv'])] if f.is_file()},
        Gamma_C_db=0,relay_uavs=2,energy_components=6,sites=118,external_structure_used=False))
    adapter.core.RESULTS_Q2=root/'q2';adapter.shift.RESULTS_Q2=root/'q2';adapter.exporter.RESULTS_Q2=root/'q2'
    return e

def materialize(e,columns,shifts,fixed=False):
    import numpy as np
    groups=[dict(site_id=c['site_id'],task_ids=c['task_ids']) for c in columns]
    m=adapter.core.Timing(e,e.pid,groups,objective='makespan',late_budget=1e-4)
    x=np.zeros(m.dim)
    for sid,v in shifts.items():x[m.idx[sid]]=v
    selected=[sortie_column(e,e.pid,g['site_id'],g['task_ids'],shifts) for g in groups]
    assert all(selected)
    color_intervals(selected,'preparation_start_s','uav_available_s',['R01','R02'],'relay_id')
    answer=m.materialize(x,sequences_for(selected),[])
    assert answer and answer['metrics']['J_late']<=1e-4
    if fixed:
        assert all(v==0 for v in shifts.values())
        frame=adapter.read(e.base/'q2_sorties.csv')
        answer['assignments']={r.sortie_id:dict(uav_id=r.uav_id,battery_id=r.battery_id) for r in frame.itertuples()}
    return answer

def save_answer(e,answer,ident):
    adapter.export_local(e,copy.deepcopy(answer),ident)
    package=e.dest/'solutions'/ident
    valid=audit(e.root,e.pid,package)
    assert valid['hard_violations']==0 and valid['uncovered_sample_count']==0 and valid['J_late']<=1e-4
    write(package/f'plan_status_{e.pid}.json',dict(status='P1_3C_Q3_INDEPENDENTLY_VALIDATED',validation_sha256=digest(package/'validation_0.5.json')))
    return dict(id=ident,metrics=answer['metrics'],package=str(package.relative_to(ROOT)),validation=valid,
        validation_sha256=digest(package/'validation_0.5.json'))
