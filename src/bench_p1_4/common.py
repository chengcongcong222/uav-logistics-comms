"""P1.4 isolated cold communication and original execution validation."""
import copy,json,shutil,time,os
from pathlib import Path
from src.bench_p1.common import ROOT,write,digest,signature
from src.bench_p1 import q3_adapter as adapter
from src.bench_p1_3b.common import install_input_guard
from src.bench_p1_2.driver import audit
from src.q3.e6_resources import sortie_column,color_intervals
from src.q3.e7_core import sequences_for
from src.bench_p1_3c.common import materialize

OUT=ROOT/os.environ.get('P14_OUTPUT','results/p1_4')
SEED=26092511
CAP=float(os.environ.get('P14_CAP_S','6500'))
MAX_RELAY=3
def read(p):return json.loads(Path(p).read_text())

def engine(pid):
    root=OUT/'screening'/pid;root.mkdir(parents=True,exist_ok=True)
    source=OUT/'q2/pareto_schedules'/pid;target=root/'q2/pareto_schedules'/pid
    if not target.exists():shutil.copytree(source,target)
    cached=root/'q3'/pid
    cpu=time.process_time();wall=time.monotonic();reuse=(cached/'candidate_summary.json').exists()
    if reuse:
        class SavedEngine(adapter.Engine):
            def demands(self,frame):return adapter.read(cached/'guarded_atomic_tasks.csv')
        e=SavedEngine(root,pid,lambda stage:print(pid,stage,flush=True))
        for row in adapter.read(cached/'candidate_pairs.csv').to_dict('records'):e.edges[pid][row['atomic_task_id']][row['site_id']]=row
    else:
        e=adapter.Engine(root,pid,lambda stage:print(pid,stage,flush=True));e.pool()
    assert len(e.sites)==118
    record=dict(pid=pid,cold_build=not reuse,own_structure_cache_only=True,cpu_s=time.process_time()-cpu,wall_s=time.monotonic()-wall,
        site_count=118,atoms=len(e.atoms),Gamma_C_db=0,source_hashes={p.name:digest(p) for p in source.glob('*') if p.is_file()})
    name='reuse' if reuse else 'cold';write(root/f'{name}_build.json',record)
    adapter.core.RESULTS_Q2=root/'q2';adapter.shift.RESULTS_Q2=root/'q2';adapter.exporter.RESULTS_Q2=root/'q2'
    return e

def save_answer(e,answer,ident):
    assert answer['metrics']['J_late']<=1e-8 and answer['metrics']['relay_sorties']<=MAX_RELAY
    assert answer['metrics']['joint_makespan_s']<=CAP+1e-7
    adapter.export_local(e,copy.deepcopy(answer),ident);package=e.dest/'solutions'/ident;valid=audit(e.root,e.pid,package)
    assert valid['hard_violations']==0 and valid['uncovered_sample_count']==0 and valid['J_late']<=1e-8
    write(package/f'plan_status_{e.pid}.json',dict(status='P1_4_Q3_INDEPENDENTLY_VALIDATED',validation_sha256=digest(package/'validation_0.5.json')))
    return dict(id=ident,metrics=answer['metrics'],cap_s=CAP,package=str(package.relative_to(ROOT)),validation=valid,validation_sha256=digest(package/'validation_0.5.json'))
