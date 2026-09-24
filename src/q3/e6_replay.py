"""Replay the committed E6 execution witness without running candidate search."""
from src.q3.e6_guard import *
from src.q3.e6_order_search import OrderTiming
from src.q3.e6_export import export_plan


def replay():
    witness=json.loads((OUT/'execution_witness.json').read_text())
    manifest=json.loads((OUT/'input_manifest.json').read_text())
    for name,digest in manifest['hashes'].items():
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest,name
    engine=ResourceEngine()
    for pid in witness:load_pool(engine,pid)
    apply_guards(engine)
    for pid,case in witness.items():
        groups=case['groups'];sequences=case['sequences']
        checks=[]
        for group in groups:
            for aid in group['task_ids']:
                record=engine.check_task(aid,group['site_id'])
                assert record is not None,(pid,aid,group['site_id'])
                checks.append(record)
        result=OrderTiming(engine,pid,groups).solve(sequences,lexicographic=True)
        assert result is not None,pid
        _,shifts,selected=result
        assert abs(sum(shifts.values())-case['expected_total_shift_s'])<1e-4
        assign_and_save(engine,pid,selected,shifts,'SHIFTED_SCHEDULE_FEASIBLE')
        write_csv(OUT/f'guarded_selected_pairs_{pid}.csv',checks)
        export_plan(pid)
    print('Execution witness reproduced. Run independent validators before issuing gate.',flush=True)


if __name__=='__main__':replay()
