#!/usr/bin/env python3
"""Independent Q2 transport-trace validator. Success => E3_TRACE_VALID."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path("/home/ccc/projects/uav-logistics-comms")
sys.path.insert(0, str(ROOT))

from src.common.paths import EXPORT_DIR, PROCESSED_DIR, RESULTS_Q2  # noqa: E402

TOL = 1e-3


def fail(msg: str) -> None:
    print(f"E3_TRACE_INVALID: {msg}")
    raise SystemExit(1)


def phase_duration(tr: pd.DataFrame, mode: str) -> float:
    """Sum (end.time - start.time) for start/end pairs of `mode`."""
    total = 0.0
    starts = tr[(tr["mode"] == mode) & (tr["phase_role"] == "start")]
    ends = tr[(tr["mode"] == mode) & (tr["phase_role"] == "end")]
    if len(starts) != len(ends):
        fail(f"unpaired {mode} markers {len(starts)}/{len(ends)}")
    for (_, a), (_, b) in zip(starts.iterrows(), ends.iterrows()):
        total += float(b.time) - float(a.time)
    return total


def main() -> None:
    trace = pd.read_csv(EXPORT_DIR / "q2_transport_trace.csv")
    sorties = pd.read_csv(RESULTS_Q2 / "q2_sorties.csv")
    delivery = pd.read_csv(RESULTS_Q2 / "q2_box_delivery.csv")
    nodes = pd.read_csv(PROCESSED_DIR / "nodes.csv").set_index("node_id")
    types = pd.read_csv(PROCESSED_DIR / "transport_uav_types.csv").set_index("uav_type")
    geom = pd.read_csv(PROCESSED_DIR / "route_geometry.csv").set_index(["from_id", "to_id"])

    if set(trace.task_id) != set(sorties.sortie_id):
        fail("trace/sortie id mismatch")

    x01, y01 = float(nodes.loc["O01", "x_m"]), float(nodes.loc["O01", "y_m"])
    z01 = float(nodes.loc["O01", "ground_elevation_m"])

    for s in sorties.itertuples():
        tr = (
            trace[trace.task_id == s.sortie_id]
            .sort_values(["time", "mode", "phase_role"], kind="mergesort")
            .reset_index(drop=True)
        )
        if (tr.time.diff().dropna() < -TOL).any():
            fail(f"time not non-decreasing {s.sortie_id}")

        # takeoff / return at O01
        if abs(float(tr.iloc[0].x) - x01) > 1e-3:
            fail(f"start not O01 {s.sortie_id}")
        ret = tr[tr["mode"] == "return"]
        if ret.empty:
            fail(f"missing return {s.sortie_id}")
        last = ret.iloc[-1]
        if abs(float(last.x) - x01) > 1e-3 or abs(float(last.y) - y01) > 1e-3:
            fail(f"return xy not O01 {s.sortie_id}")
        if abs(float(last.z) - z01) > 1e-2:
            fail(f"return z not O01 ground {s.sortie_id}")
        if abs(float(last.time) - float(s.return_s)) > TOL:
            fail(f"return time {s.sortie_id}: {last.time} vs {s.return_s}")

        seq = str(s.service_sequence).split(">")
        t = types.loc[s.uav_type]
        path = ["O01"] + seq + ["O01"]

        # handover_end == delivery_time
        for svc in seq:
            sx, sy = float(nodes.loc[svc, "x_m"]), float(nodes.loc[svc, "y_m"])
            he = tr[(tr["mode"] == "handover_end") & ((tr.x - sx).abs() < 1.0)]
            if he.empty:
                fail(f"missing handover_end {s.sortie_id} {svc}")
            td = delivery[(delivery.sortie_id == s.sortie_id) & (delivery.service_id == svc)]
            if td.empty:
                fail(f"missing delivery {s.sortie_id} {svc}")
            if abs(float(he.iloc[0].time) - float(td.delivery_time_s.iloc[0])) > TOL:
                fail(f"handover_end != delivery {s.sortie_id} {svc}")
            # handover interval positive and matches formula
            hs = tr[(tr["mode"] == "handover_start") & ((tr.x - sx).abs() < 1.0)]
            if hs.empty:
                fail(f"missing handover_start {s.sortie_id} {svc}")
            n_boxes = int(td.shape[0])
            exp_h = float(t.handover_base_s) + n_boxes * float(t.handover_per_box_s)
            got_h = float(he.iloc[0].time) - float(hs.iloc[0].time)
            if abs(got_h - exp_h) > TOL:
                fail(f"handover duration {s.sortie_id} {svc} {got_h} vs {exp_h}")

        # phase durations vs frozen speeds
        climb_t = phase_duration(tr, "climb")
        cruise_t = phase_duration(tr, "cruise")
        desc_t = phase_duration(tr, "descent")
        exp_u = exp_c = exp_d = 0.0
        for a, b in zip(path[:-1], path[1:]):
            row = geom.loc[(a, b)]
            exp_u += float(row.climb_height_m) / float(t.max_climb_mps)
            exp_c += float(row.horizontal_distance_m) / float(t.cruise_speed_mps)
            exp_d += float(row.descent_height_m) / float(t.max_descend_mps)
        if abs(climb_t - exp_u) > 1e-2:
            fail(f"climb duration {s.sortie_id} {climb_t} vs {exp_u}")
        if abs(cruise_t - exp_c) > 1e-2:
            fail(f"cruise duration {s.sortie_id} {cruise_t} vs {exp_c}")
        if abs(desc_t - exp_d) > 1e-2:
            fail(f"descent duration {s.sortie_id} {desc_t} vs {exp_d}")

        # no teleport on distinct-time transitions
        for i in range(len(tr) - 1):
            a, b = tr.iloc[i], tr.iloc[i + 1]
            dx = abs(float(a.x) - float(b.x))
            dy = abs(float(a.y) - float(b.y))
            dz = abs(float(a.z) - float(b.z))
            dt = float(b.time) - float(a.time)
            if dx + dy + dz > 0.5 and dt <= TOL and str(a["mode"]) != str(b["mode"]):
                # mode switch at same time is allowed if same coordinate only
                fail(f"teleport or coord jump {s.sortie_id} t={a.time}")
            if dt < -TOL:
                fail(f"time reversal {s.sortie_id}")

        # active interval coverage
        if abs(float(tr.time.min()) - float(s.preparation_start_s)) > TOL:
            fail(f"prep start {s.sortie_id}")
        if float(s.return_s) > float(tr.time.max()) + TOL:
            fail(f"return after trace end {s.sortie_id}")

    print("E3_TRACE_VALID")


if __name__ == "__main__":
    main()
