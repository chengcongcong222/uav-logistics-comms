#!/usr/bin/env python3
from pathlib import Path
import sys
ROOT = Path("/home/ccc/projects/uav-logistics-comms")
sys.path.insert(0, str(ROOT))
from src.q2.solve_q2 import load_tables
from src.q2.evaluator import MissionEvaluator
from src.q2.scheduler import ResourceDecoder
from src.q2.initial_solution import build_b0
from src.q2.evaluator_sol import evaluate_solution

tables = load_tables()
ev = MissionEvaluator(tables, 0.2)
dec = ResourceDecoder(tables, 0.2)
# try single mission decode
from src.q2.initial_solution import pack_key
items = list(tables["boxes"][tables["boxes"].service_id == "S001"].box_id)
print("S001 boxes", len(items))
for g in tables["types"].index:
    m = ev.evaluate_mission(g, {"S001": items}, ["S001"])
    print(g, "ok" if m else None, None if not m else (m.relative_return_time, m.energy_kg if hasattr(m,"energy_kg") else m.energy_kwh, m.hard_deadline_latest_start))

# step through B0 packing only
from src.q2.initial_solution import build_b0
try:
    b0 = build_b0(ev, dec)
    print("B0 ok", b0.metrics)
except Exception as e:
    print("B0 fail", e)

# try decode one by one to find failure
raw = []
types = list(tables["types"].index)
for service in sorted(tables["boxes"].service_id.unique()):
    remaining = list(tables["boxes"][tables["boxes"].service_id == service].box_id)
    while remaining:
        best = None
        for g in types:
            order = sorted(remaining, key=lambda b: -float(ev.box_idx.loc[b, "mass_kg"]))
            chosen = []
            mass = vol = 0.0
            t = ev.types.loc[g]
            for b in order:
                bm = float(ev.box_idx.loc[b, "mass_kg"]); bv = float(ev.box_idx.loc[b, "volume_m3"])
                if mass + bm <= t.max_payload_kg + 1e-9 and vol + bv <= t.cargo_volume_m3 + 1e-9:
                    chosen.append(b); mass += bm; vol += bv
            if not chosen:
                continue
            m = ev.evaluate_mission(g, {service: chosen}, [service])
            if m is None:
                for k in range(len(chosen)-1, 0, -1):
                    m = ev.evaluate_mission(g, {service: chosen[:k]}, [service])
                    if m:
                        chosen = chosen[:k]; break
                else:
                    continue
            cand = (len(chosen), -m.energy_kwh, -m.relative_return_time, g, chosen)
            if best is None or cand[:4] > best[:4]:
                best = cand
        if best is None:
            print("cannot pack", service, remaining); break
        g, chosen = best[3], best[4]
        raw.append(pack_key(g, [service], {service: chosen}))
        remaining = [b for b in remaining if b not in set(chosen)]
        print("packed", service, g, len(chosen), "left", len(remaining))

print("missions", len(raw))
# decode one by one
from src.q2.evaluator import GateStats
ms = []
for spec in raw:
    m = ev.evaluate_mission(spec["uav_type"], spec["boxes_by_service"], spec["service_sequence"])
    ms.append(m)
ms.sort(key=lambda m: (m.hard_deadline_latest_start if m.hard_deadline_latest_start is not None else 1e18, m.relative_return_time))
st = dec.init_state()
for i, m in enumerate(ms):
    out, st2, ok = dec.decode_order([m], st)
    print(i, m.mission_id if m.mission_id else "", m.uav_type, m.service_sequence, "latest", m.hard_deadline_latest_start, "ret", m.relative_return_time, "ok", ok)
    if not ok:
        print("FAILED at", i, m.uav_type, m.service_sequence, m.boxes_by_service)
        break
    st = st2
