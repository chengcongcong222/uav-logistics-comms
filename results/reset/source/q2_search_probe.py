"""Minimal behavior probes of Q2 code read at commit badc8a4.
This does not solve the contest instance or run the complete repository.
_insert_box and _remove_boxes below reproduce the retrieved function bodies,
with type annotations/docstrings removed and dependency-only stubs provided.
"""
import copy
import json
from types import SimpleNamespace


def pack_key(g, seq, by):
    return dict(uav_type=g, service_sequence=list(seq),
                boxes_by_service={k: list(v) for k, v in by.items()})


def _insert_box(evaluator, ms, box_id, rng, mode):
    r = evaluator.box_idx.loc[box_id]
    svc = r['service_id']
    cands = []
    types = list(evaluator.types.index)
    for i, m in enumerate(ms):
        if svc in m['boxes_by_service']:
            for g in [m['uav_type']]:
                by = {s: list(bl) for s, bl in m['boxes_by_service'].items()}
                by[svc] = by[svc] + [box_id]
                trial = copy.deepcopy(ms)
                trial[i] = pack_key(g, m['service_sequence'], by)
                cands.append(trial)
    for i, m in enumerate(ms):
        if svc in m['boxes_by_service']:
            continue
        positions = list(range(len(m['service_sequence']) + 1))
        if len(positions) > 3:
            positions = positions[:2] + positions[-1:]
        for pos in positions:
            for g in [m['uav_type']]:
                seq = m['service_sequence'][:pos] + [svc] + m['service_sequence'][pos:]
                by = {s: list(bl) for s, bl in m['boxes_by_service'].items()}
                by[svc] = [box_id]
                trial = copy.deepcopy(ms)
                trial[i] = pack_key(g, seq, by)
                cands.append(trial)
    for g in types:
        trial = copy.deepcopy(ms)
        trial.append(pack_key(g, [svc], {svc: [box_id]}))
        cands.append(trial)
        break
    for g in types[1:2]:
        trial = copy.deepcopy(ms)
        trial.append(pack_key(g, [svc], {svc: [box_id]}))
        cands.append(trial)
    return cands[:12]


def _remove_boxes(ms, rm):
    out = []
    for m in ms:
        by = {}
        for s, bl in m['boxes_by_service'].items():
            keep = [b for b in bl if b not in rm]
            if keep:
                by[s] = keep
        if by:
            m2 = copy.deepcopy(m)
            m2['boxes_by_service'] = by
            m2['service_sequence'] = list(by.keys())
            out.append(m2)
    return out, sorted(rm)


def main():
    ev = SimpleNamespace(types=SimpleNamespace(index=['A','B','C']),
                         box_idx=SimpleNamespace(loc={'X': {'service_id': 'SX'}}))
    a = _insert_box(ev, [], 'X', None, 'same')
    new_types = [x[0]['uav_type'] for x in a]
    assert new_types == ['A', 'B']
    ms = [pack_key('A', [f'S{i}'], {f'S{i}': [f'B{i}']}) for i in range(14)]
    b = _insert_box(ev, ms, 'X', None, 'same')
    touched = sorted(set(i for trial in b for i, m in enumerate(trial)
                         if 'SX' in m['boxes_by_service']))
    assert len(b) == 12 and touched == list(range(6))
    assert all(len(x) == 14 for x in b)
    c = pack_key('C', ['S2','S1'], {'S1':['B1','B2'], 'S2':['B3']})
    after, _ = _remove_boxes([c], {'B2'})
    assert after[0]['service_sequence'] == ['S1','S2']
    options = [dict(J_late=100, J_time=.2, makespan=100, energy=10, sorties=2),
               dict(J_late=0, J_time=.3, makespan=100, energy=10, sorties=2)]
    selected = min(options, key=lambda m: (m['J_time'],m['makespan'],m['energy'],m['sorties']))
    assert selected['J_late'] == 100
    return dict(commit='badc8a4282f9935018c837e52b32b86539c96071',
      scope='isolated behavior probes, not full-instance optimization',
      empty_solution_new_mission_types=new_types,
      fourteen_missions_retained_insertions=len(b),
      fourteen_missions_touched_indices=touched,
      fourteen_missions_new_mission_probe_retained=False,
      surviving_route_order_before=c['service_sequence'],
      surviving_route_order_after=after[0]['service_sequence'],
      repair_sort_can_prefer_late_100_over_late_0=True,
      tests_passed=4)

if __name__=='__main__':
    result=main()
    print(json.dumps(result,ensure_ascii=False,indent=2))
