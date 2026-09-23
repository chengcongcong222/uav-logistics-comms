#!/usr/bin/env python3
"""E1 automatic fact validation. Exit 0 => E1_DATA_VALIDATION_OK."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path("/home/ccc/projects/uav-logistics-comms")
sys.path.insert(0, str(ROOT))

from src.common.data_loader import write_processed  # noqa: E402
from src.common.dem_audit import main as dem_audit_main  # noqa: E402

EXPECTED = {
    "dispatch_centers": 1,
    "service_areas": 15,
    "boxes": 80,
    "transport_uavs": 8,
    "type_A": 4,
    "type_B": 2,
    "type_C": 2,
    "relay_uavs": 2,
    "batt_A": 6,
    "batt_B": 4,
    "batt_C": 4,
    "relay_energy": 6,
    "first_batch_boxes": 30,
    "total_mass_kg": 758.0,
    "total_volume_m3": 2.011,
}

MATERIAL_EXPECT = {
    "医疗物资": {"boxes": 16, "mass_kg": 48.0, "volume_m3": 0.192},
    "饮用水": {"boxes": 36, "mass_kg": 504.0, "volume_m3": 0.972},
    "应急食品": {"boxes": 19, "mass_kg": 152.0, "volume_m3": 0.532},
    "生活卫生用品": {"boxes": 9, "mass_kg": 54.0, "volume_m3": 0.315},
}


def fail(msg: str) -> None:
    print(f"E1_DATA_BLOCKED: {msg}")
    raise SystemExit(1)


def approx(a: float, b: float, tol: float = 1e-6) -> bool:
    return abs(a - b) <= tol


def main() -> None:
    write_processed()
    dem_audit_main()

    nodes = pd.read_csv(ROOT / "data/processed/nodes.csv")
    boxes = pd.read_csv(ROOT / "data/processed/boxes.csv")
    uavs = pd.read_csv(ROOT / "data/processed/transport_uavs.csv")
    types = pd.read_csv(ROOT / "data/processed/transport_uav_types.csv")
    batteries = pd.read_csv(ROOT / "data/processed/transport_batteries.csv")
    relays = pd.read_csv(ROOT / "data/processed/relay_uavs.csv")
    energy = pd.read_csv(ROOT / "data/processed/relay_energy_components.csv")
    comm = json.loads((ROOT / "data/processed/communication_parameters.json").read_text(encoding="utf-8"))

    n_dc = int((nodes["node_type"] == "dispatch_center").sum())
    n_sa = int((nodes["node_type"] == "service_area").sum())
    checks = [
        ("dispatch_centers", n_dc, EXPECTED["dispatch_centers"]),
        ("service_areas", n_sa, EXPECTED["service_areas"]),
        ("boxes", len(boxes), EXPECTED["boxes"]),
        ("transport_uavs", len(uavs), EXPECTED["transport_uavs"]),
        ("type_A", int((uavs["uav_type"] == "A").sum()), EXPECTED["type_A"]),
        ("type_B", int((uavs["uav_type"] == "B").sum()), EXPECTED["type_B"]),
        ("type_C", int((uavs["uav_type"] == "C").sum()), EXPECTED["type_C"]),
        ("relay_uavs", len(relays), EXPECTED["relay_uavs"]),
        ("batt_A", int(batteries.loc[batteries["uav_type"] == "A", "battery_pool_count"].iloc[0]), EXPECTED["batt_A"]),
        ("batt_B", int(batteries.loc[batteries["uav_type"] == "B", "battery_pool_count"].iloc[0]), EXPECTED["batt_B"]),
        ("batt_C", int(batteries.loc[batteries["uav_type"] == "C", "battery_pool_count"].iloc[0]), EXPECTED["batt_C"]),
        ("relay_energy", int(energy["energy_pool_count"].sum()), EXPECTED["relay_energy"]),
        ("first_batch_boxes", int(boxes["is_first_batch"].sum()), EXPECTED["first_batch_boxes"]),
    ]
    for name, got, exp in checks:
        if got != exp:
            fail(f"{name}: got {got}, expected {exp}")

    total_mass = float(boxes["mass_kg"].sum())
    total_vol = float(boxes["volume_m3"].sum())
    if not approx(total_mass, EXPECTED["total_mass_kg"], 1e-6):
        fail(f"total_mass_kg: got {total_mass}, expected {EXPECTED['total_mass_kg']}")
    if not approx(total_vol, EXPECTED["total_volume_m3"], 1e-6):
        fail(f"total_volume_m3: got {total_vol}, expected {EXPECTED['total_volume_m3']}")

    for mat, exp in MATERIAL_EXPECT.items():
        sub = boxes[boxes["material_type"] == mat]
        if len(sub) != exp["boxes"]:
            fail(f"{mat} boxes: got {len(sub)}, expected {exp['boxes']}")
        if not approx(float(sub["mass_kg"].sum()), exp["mass_kg"]):
            fail(f"{mat} mass: got {sub['mass_kg'].sum()}, expected {exp['mass_kg']}")
        if not approx(float(sub["volume_m3"].sum()), exp["volume_m3"]):
            fail(f"{mat} volume: got {sub['volume_m3'].sum()}, expected {exp['volume_m3']}")

    # UTM validity
    if not bool(nodes["utm49n_valid"].all()):
        fail("some nodes outside UTM 49N validity range")

    # DEM elevation: block only on large index/coord-like errors (>80 m)
    elev = pd.read_csv(ROOT / "results/e1/node_dem_elevation_check.csv")
    max_diff = float(elev["difference_m"].abs().max())
    if max_diff > 80.0:
        fail(f"node DEM elevation difference too large: {max_diff:.3f} m")

    if "endpoints" not in comm or not comm["endpoints"]:
        fail("communication parameters missing endpoints")

    print("E1_FACTS_OK")
    print(f"boxes={len(boxes)} total_mass={total_mass} total_volume={total_vol}")
    print(f"node_elev_diff_abs_max={max_diff:.3f}")
    print("E1_DATA_VALIDATION_OK")


if __name__ == "__main__":
    main()
