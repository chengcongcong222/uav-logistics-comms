"""Mission physics evaluation with T1–T5 gates (uses frozen energy model)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pandas as pd

from src.common.flight_time import handover_time_s, leg_flight_time_s, load_time_s
from src.common.transport_energy import leg_energy_kwh, return_reserve_ok
from src.q2.mission import Mission


@dataclass
class GateStats:
    generated: int = 0
    failed_t1: int = 0
    failed_t2: int = 0
    failed_t3: int = 0
    failed_t4: int = 0
    failed_t5: int = 0
    accepted: int = 0

    def as_row(self, operator: str) -> dict:
        return {
            "operator": operator,
            "generated": self.generated,
            "failed_mass": self.failed_t2,
            "failed_volume": self.failed_t3,
            "failed_energy": self.failed_t4,
            "failed_relative_deadline": self.failed_t5,
            "failed_service_consistency": self.failed_t1,
            "accepted_candidate": self.accepted,
        }


class MissionEvaluator:
    def __init__(self, tables: dict, rho: float = 0.20):
        self.types: pd.DataFrame = tables["types"]
        self.nodes: pd.DataFrame = tables["nodes"]
        self.geom: pd.DataFrame = tables["geom"]
        self.boxes: pd.DataFrame = tables["boxes"]
        self.rho = rho
        self.box_idx = self.boxes.set_index("box_id")
        self.geom_idx = self.geom.set_index(["from_id", "to_id"])

    def hard_deadline(self, box_id: str) -> Optional[float]:
        r = self.box_idx.loc[box_id]
        vals = []
        if pd.notna(r.expected_deadline_s) and bool(r.is_medical):
            vals.append(float(r.expected_deadline_s))
        if pd.notna(r.first_deadline_s) and bool(r.is_first_batch):
            vals.append(float(r.first_deadline_s))
        return min(vals) if vals else None

    def leg(self, i: str, j: str) -> pd.Series:
        return self.geom_idx.loc[(i, j)]

    def evaluate_mission(
        self,
        uav_type: str,
        boxes_by_service: dict[str, list[str]],
        service_sequence: list[str],
        stats: Optional[GateStats] = None,
        operator: str = "eval",
    ) -> Optional[Mission]:
        if stats is not None:
            stats.generated += 1
        # T1: non-empty, consistent services, unique boxes
        all_boxes: list[str] = []
        for s in service_sequence:
            bl = boxes_by_service.get(s, [])
            if not bl:
                if stats:
                    stats.failed_t1 += 1
                return None
            for b in bl:
                if self.box_idx.loc[b, "service_id"] != s:
                    if stats:
                        stats.failed_t1 += 1
                    return None
            all_boxes.extend(bl)
        if len(all_boxes) != len(set(all_boxes)):
            if stats:
                stats.failed_t1 += 1
            return None

        t = self.types.loc[uav_type]
        mass0 = float(self.box_idx.loc[all_boxes, "mass_kg"].sum())
        vol0 = float(self.box_idx.loc[all_boxes, "volume_m3"].sum())
        if mass0 > float(t.max_payload_kg) + 1e-9:
            if stats:
                stats.failed_t2 += 1
            return None
        if vol0 > float(t.cargo_volume_m3) + 1e-9:
            if stats:
                stats.failed_t3 += 1
            return None

        e_use = float(t.battery_energy_kwh)
        empty = float(t.empty_mass_with_battery_kg)
        path = ["O01"] + list(service_sequence) + ["O01"]
        payload = mass0
        energy = 0.0
        t_rel = 0.0
        n_total = len(all_boxes)
        # prep + load
        t_rel += float(t.prep_time_s) + load_time_s(n_total, float(t.load_time_per_box_s))
        takeoff_rel = t_rel
        delivery_times: dict[str, float] = {}
        for si, (a, b) in enumerate(zip(path[:-1], path[1:])):
            row = self.leg(a, b)
            q = payload if b != "O01" else 0.0
            # after drop at b, payload decreases before next leg — energy uses q on this leg
            e_leg = leg_energy_kwh(
                float(row.horizontal_distance_m),
                float(row.climb_height_m),
                float(row.descent_height_m),
                q,
                empty,
                float(t.range_empty_m),
                float(t.range_full_m),
                float(t.max_payload_kg),
                e_use,
                float(t.climb_energy_eff),
                float(t.descend_energy_eff),
            )
            energy += e_leg
            t_leg = leg_flight_time_s(
                float(row.climb_height_m),
                float(row.horizontal_distance_m),
                float(row.descent_height_m),
                float(t.max_climb_mps),
                float(t.cruise_speed_mps),
                float(t.max_descend_mps),
            )
            t_rel += t_leg
            if b != "O01":
                service = b
                bl = boxes_by_service[service]
                t_rel += handover_time_s(
                    len(bl), float(t.handover_base_s), float(t.handover_per_box_s)
                )
                delivery_times[service] = t_rel
                payload -= float(self.box_idx.loc[bl, "mass_kg"].sum())
        return_rel = t_rel
        if not return_reserve_ok(energy, e_use, self.rho):
            if stats:
                stats.failed_t4 += 1
            return None

        # T5 relative deadlines
        for service, bl in boxes_by_service.items():
            td = delivery_times[service]
            for b in bl:
                hd = self.hard_deadline(b)
                if hd is not None and td > hd + 1e-9:
                    if stats:
                        stats.failed_t5 += 1
                    return None

        if stats:
            stats.accepted += 1

        # hard latest start
        latest = None
        for service, bl in boxes_by_service.items():
            for b in bl:
                hd = self.hard_deadline(b)
                if hd is None:
                    continue
                ls = hd - delivery_times[service]
                latest = ls if latest is None else min(latest, ls)

        return Mission(
            mission_id="",
            uav_type=uav_type,
            box_ids=all_boxes,
            service_sequence=list(service_sequence),
            boxes_by_service={k: list(v) for k, v in boxes_by_service.items()},
            initial_payload_kg=mass0,
            initial_volume_m3=vol0,
            relative_prep_start=0.0,
            relative_takeoff_time=takeoff_rel,
            relative_delivery_times=delivery_times,
            relative_return_time=return_rel,
            energy_kwh=energy,
            energy_margin_kwh=(1 - self.rho) * e_use - energy,
            hard_deadline_latest_start=latest,
        )

    def mission_objective_tuple(self, mission: Mission) -> tuple:
        """Internal ranking only: earlier completion / lower energy."""
        return (mission.relative_return_time, mission.energy_kwh, -len(mission.box_ids))
