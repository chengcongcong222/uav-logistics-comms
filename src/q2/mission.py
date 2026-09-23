"""Mission object for multi-stop transport sorties (shared with future Q3)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Mission:
    mission_id: str
    uav_type: str
    box_ids: list[str]
    service_sequence: list[str]
    boxes_by_service: dict[str, list[str]]
    initial_payload_kg: float
    initial_volume_m3: float
    # relative times (mission start = 0)
    relative_prep_start: float = 0.0
    relative_takeoff_time: float = 0.0
    relative_delivery_times: dict[str, float] = field(default_factory=dict)
    relative_return_time: float = 0.0
    energy_kwh: float = 0.0
    energy_margin_kwh: float = 0.0
    hard_deadline_latest_start: Optional[float] = None
    # decoder-filled absolute schedule
    uav_id: Optional[str] = None
    battery_id: Optional[str] = None
    preparation_start_s: float = 0.0
    takeoff_s: float = 0.0
    return_s: float = 0.0
    delivery_times_s: dict[str, float] = field(default_factory=dict)

    def hard_boxes(self, box_hard: dict[str, Optional[float]]) -> list[str]:
        return [b for b in self.box_ids if box_hard.get(b) is not None]
