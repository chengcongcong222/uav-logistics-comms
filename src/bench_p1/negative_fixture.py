"""Hard-deadline negative control preserving interval non-overlap."""
import json,sys
from src.bench_p1.common import ROOT,OUT,write
from src.reset.geometry import tables
from src.q2.mission import Mission
from src.q2.evaluator import MissionEvaluator
from src.xb1.audit import export
def main():
    sys.path.insert(0,str(ROOT/'validation/mathematical'))
    from xb1_validate import check_package
    tab=tables();ev=MissionEvaluator(tab);root=OUT/'negative_audit'
    source=OUT/'runs/Q2_30_v1/ALNS_26092511/q2/pareto_schedules/P0001/missions.json'
    ms=[Mission(**x) for x in json.loads(source.read_text())]
    delta=min(ev.hard_deadline(b)-m.delivery_times_s[s] for m in ms for s,bs in m.boxes_by_service.items() for b in bs if ev.hard_deadline(b) is not None)+1
    for m in ms:
        m.preparation_start_s+=delta;m.takeoff_s+=delta;m.return_s+=delta;m.delivery_times_s={s:t+delta for s,t in m.delivery_times_s.items()}
    dest=root/'q2/pareto_schedules/HARD';export(ms,tab,dest,'HARD')
    try:check_package(dest,'HARD',tab['geom'])
    except Exception as exc:
        assert 'Hard deadline violations' in str(exc),repr(exc)
        write(root/'result.json',dict(status='EXPECTED_HARD_DEADLINE_REJECTION',shift_s=delta,error=str(exc),case='Whole schedule translated: no new interval overlap, earliest hard deadline exceeded by exactly one second'))
        return
    raise AssertionError('Hard deadline corruption passed')
if __name__=='__main__':main()
