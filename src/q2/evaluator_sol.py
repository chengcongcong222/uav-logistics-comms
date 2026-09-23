"""Solution representation and evaluation for Q2 ALNS."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import pandas as pd

from src.q2.evaluator import GateStats, MissionEvaluator
from src.q2.mission import Mission
from src.q2.scheduler import ResourceDecoder


@dataclass
class Solution:
    # list of missions as (uav_type, service_sequence, boxes_by_service)
    missions: list[dict] = field(default_factory=list)
    decoded: list[Mission] = field(default_factory=list)
    metrics: dict = field(default_factory=dict)
    gate_stats: GateStats = field(default_factory=GateStats)


def pack_key(uav_type: str, service_sequence: list[str], boxes_by_service: dict[str, list[str]]) -> dict:
    return {
        "uav_type": uav_type,
        "service_sequence": list(service_sequence),
        "boxes_by_service": {k: list(v) for k, v in boxes_by_service.items()},
    }


def evaluate_solution(
    raw_missions: list[dict],
    evaluator: MissionEvaluator,
    decoder: ResourceDecoder,
    gate_stats: Optional[GateStats] = None,
) -> Optional[Solution]:
    gs = gate_stats or GateStats()
    missions: list[Mission] = []
    for spec in raw_missions:
        m = evaluator.evaluate_mission(
            spec["uav_type"], spec["boxes_by_service"], spec["service_sequence"], stats=gs, operator="sol"
        )
        if m is None:
            return None
        missions.append(m)

    # order by hard latest start then weighted expected deadline
    box = evaluator.box_idx

    def sort_key(m: Mission):
        ls = m.hard_deadline_latest_start if m.hard_deadline_latest_start is not None else 1e18
        # soft urgency
        urg = 0.0
        for b in m.box_ids:
            r = box.loc[b]
            w = float(r.priority_weight)
            d = float(r.expected_deadline_s) if pd.notna(r.expected_deadline_s) else 1e18
            urg += w / max(d, 1.0)
        return (ls, -urg, m.initial_payload_kg)

    missions.sort(key=sort_key)
    decoded, _st, ok = decoder.decode_order(missions)
    if not ok or len(decoded) != len(missions):
        return None

    # metrics
    num = den = 0.0
    soft_late_count = 0
    soft_sum = 0.0
    max_soft = 0.0
    for m in decoded:
        for svc, bl in m.boxes_by_service.items():
            td = m.delivery_times_s[svc]
            for b in bl:
                r = box.loc[b]
                if pd.notna(r.expected_deadline_s):
                    w = float(r.priority_weight)
                    d = float(r.expected_deadline_s)
                    num += w * (td / d)
                    den += w
                    late = max(0.0, td - d)
                    if late > 1e-9:
                        soft_late_count += 1
                        soft_sum += late
                        max_soft = max(max_soft, late)
    j_time = num / den if den > 0 else float("nan")
    metrics = {
        "J_time": j_time,
        "makespan": max(m.return_s for m in decoded),
        "energy": sum(m.energy_kwh for m in decoded),
        "sorties": len(decoded),
        "soft_late_count": soft_late_count,
        "soft_lateness_sum": soft_sum,
        "max_soft_lateness": max_soft,
    }
    return Solution(
        missions=[pack_key(m.uav_type, m.service_sequence, m.boxes_by_service) for m in decoded],
        decoded=decoded,
        metrics=metrics,
        gate_stats=gs,
    )


def internal_score(sol: Solution) -> tuple:
    m = sol.metrics
    return (0, 0.0, m["J_time"], m["makespan"], m["energy"], m["sorties"])
