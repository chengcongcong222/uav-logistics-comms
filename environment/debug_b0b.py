#!/usr/bin/env python3
from pathlib import Path
import sys
ROOT = Path("/home/ccc/projects/uav-logistics-comms")
sys.path.insert(0, str(ROOT))
from src.q2.solve_q2 import load_tables
from src.q2.evaluator import MissionEvaluator, GateStats
from src.q2.scheduler import ResourceDecoder
from src.q2.initial_solution import _pack_service
from src.q2.evaluator_sol import evaluate_solution

tables = load_tables()
ev = MissionEvaluator(tables, 0.2)
dec = ResourceDecoder(tables, 0.2)
raw = []
for service in sorted(tables["boxes"].service_id.unique()):
    items = list(tables["boxes"][tables["boxes"].service_id == service].box_id)
    part = _pack_service(ev, service, items)
    print(service, len(items), "->", len(part), "sorties")
    raw.extend(part)
print("total raw", len(raw))

# build missions and sort like evaluate_solution
ms = []
for spec in raw:
    m = ev.evaluate_mission(spec["uav_type"], spec["boxes_by_service"], spec["service_sequence"], stats=GateStats())
    if m is None:
        print("eval fail", spec)
        continue
    ms.append(m)
print("eval ok", len(ms))

def sk(m):
    ls = m.hard_deadline_latest_start if m.hard_deadline_latest_start is not None else 1e18
    return (ls, m.relative_return_time)
ms.sort(key=sk)
st = dec.init_state()
ok_count = 0
for i, m in enumerate(ms):
    out, st2, ok = dec.decode_order([m], st)
    if not ok:
        print("FAIL", i, m.uav_type, m.service_sequence, "n", len(m.box_ids), "latest", m.hard_deadline_latest_start, "ret", round(m.relative_return_time,1), "energy", round(m.energy_kwh,3))
        # show resource state
        print("  uav busy", {k:v for k,v in st.uav_busy_until.items() if v>0})
        print("  batt ready", {k:round(v,1) for k,v in st.batt_ready_at.items() if v>0})
        break
    st = st2
    ok_count += 1
    mm = out[0]
    print("OK", i, mm.uav_id, mm.battery_id, "prep", round(mm.preparation_start_s,1), "takeoff", round(mm.takeoff_s,1), "ret", round(mm.return_s,1), "latest", None if m.hard_deadline_latest_start is None else round(m.hard_deadline_latest_start,1))
print("scheduled", ok_count, "/", len(ms))

sol = evaluate_solution(raw, ev, dec)
print("evaluate_solution", sol.metrics if sol else None)
