#!/usr/bin/env python3
"""Independent Q2 validator — recomputes physics/resources without ALNS internals."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path("/home/ccc/projects/uav-logistics-comms")
sys.path.insert(0, str(ROOT))

from src.common.charging import charge_time_s  # noqa: E402
from src.common.flight_time import handover_time_s, leg_flight_time_s, load_time_s  # noqa: E402
from src.common.paths import PROCESSED_DIR, RESULTS_Q2  # noqa: E402
from src.common.transport_energy import leg_energy_kwh, return_reserve_ok  # noqa: E402


def fail(msg: str) -> None:
    print(f"E3_Q2_INVALID: {msg}")
    raise SystemExit(1)


def main() -> None:
    types = pd.read_csv(PROCESSED_DIR / "transport_uav_types.csv").set_index("uav_type")
    geom = pd.read_csv(PROCESSED_DIR / "route_geometry.csv").set_index(["from_id", "to_id"])
    boxes = pd.read_csv(PROCESSED_DIR / "boxes.csv").set_index("box_id")
    sorties = pd.read_csv(RESULTS_Q2 / "q2_sorties.csv")
    delivery = pd.read_csv(RESULTS_Q2 / "q2_box_delivery.csv")
    uav_cal = pd.read_csv(RESULTS_Q2 / "q2_uav_calendar.csv")
    bat_cal = pd.read_csv(RESULTS_Q2 / "q2_battery_calendar.csv")
    obj = pd.read_csv(RESULTS_Q2 / "q2_objectives.csv").iloc[0]

    # coverage
    if len(delivery) != 80 or delivery.box_id.nunique() != 80:
        fail("box coverage not exactly once")
    if set(delivery.box_id) != set(boxes.index):
        fail("box id set mismatch")

    # service consistency
    for r in delivery.itertuples():
        if boxes.loc[r.box_id, "service_id"] != r.service_id:
            fail(f"service mismatch {r.box_id}")

    rho = 0.20
    for s in sorties.itertuples():
        t = types.loc[s.uav_type]
        seq = str(s.service_sequence).split(">")
        if seq[0] != "O01" and seq[-1] != "O01":
            # service_sequence stored as S..>S..
            pass
        path = ["O01"] + seq + ["O01"]
        bl_by = delivery[delivery.sortie_id == s.sortie_id].groupby("service_id").box_id.apply(list).to_dict()
        all_b = [b for seqs in bl_by.values() for b in seqs]
        mass = float(boxes.loc[all_b, "mass_kg"].sum())
        vol = float(boxes.loc[all_b, "volume_m3"].sum())
        if abs(mass - s.payload_kg) > 1e-6:
            fail(f"payload mismatch {s.sortie_id}")
        if mass > float(t.max_payload_kg) + 1e-9:
            fail(f"mass {s.sortie_id}")
        if vol > float(t.cargo_volume_m3) + 1e-9:
            fail(f"volume {s.sortie_id}")
        e_use = float(t.battery_energy_kwh)
        empty = float(t.empty_mass_with_battery_kg)
        payload = mass
        energy = 0.0
        prep_load = float(t.prep_time_s) + load_time_s(len(all_b), float(t.load_time_per_box_s))
        wait = float(s.takeoff_s) - (float(s.preparation_start_s) + prep_load)
        if wait < -1e-6:
            fail(f"takeoff before prep/load done {s.sortie_id}")
        t_rel = prep_load + max(0.0, wait)  # include battery wait
        delivery_rel = {}
        for a, b in zip(path[:-1], path[1:]):
            row = geom.loc[(a, b)]
            q = payload if b != "O01" else 0.0
            energy += leg_energy_kwh(
                row.horizontal_distance_m,
                row.climb_height_m,
                row.descent_height_m,
                q,
                empty,
                t.range_empty_m,
                t.range_full_m,
                t.max_payload_kg,
                e_use,
                t.climb_energy_eff,
                t.descend_energy_eff,
            )
            t_rel += leg_flight_time_s(
                row.climb_height_m,
                row.horizontal_distance_m,
                row.descent_height_m,
                t.max_climb_mps,
                t.cruise_speed_mps,
                t.max_descend_mps,
            )
            if b != "O01":
                n = len(bl_by[b])
                t_rel += handover_time_s(n, t.handover_base_s, t.handover_per_box_s)
                delivery_rel[b] = t_rel
                payload -= float(boxes.loc[bl_by[b], "mass_kg"].sum())
        if abs(energy - s.energy_kwh) > 1e-6:
            fail(f"energy mismatch {s.sortie_id} {energy} vs {s.energy_kwh}")
        if not return_reserve_ok(energy, e_use, rho):
            fail(f"reserve {s.sortie_id}")
        if abs(t_rel - (s.return_s - s.preparation_start_s)) > 1e-6:
            fail(f"duration mismatch {s.sortie_id} calc={t_rel} got={s.return_s - s.preparation_start_s}")
        # deliveries
        for svc, rel in delivery_rel.items():
            abs_td = s.preparation_start_s + rel
            rec = delivery[(delivery.sortie_id == s.sortie_id) & (delivery.service_id == svc)]
            if rec.empty:
                fail(f"missing delivery {s.sortie_id} {svc}")
            if abs(float(rec.delivery_time_s.iloc[0]) - abs_td) > 1e-6:
                fail(f"delivery time {s.sortie_id} {svc}")
            for b in bl_by[svc]:
                r = boxes.loc[b]
                hd = None
                if bool(r.is_medical) and pd.notna(r.expected_deadline_s):
                    hd = float(r.expected_deadline_s)
                if bool(r.is_first_batch) and pd.notna(r.first_deadline_s):
                    hd2 = float(r.first_deadline_s)
                    hd = hd2 if hd is None else min(hd, hd2)
                if hd is not None and abs_td > hd + 1e-9:
                    fail(f"hard deadline {b}")

    # UAV conflicts
    for uav, g in uav_cal.groupby("uav_id"):
        g = g.sort_values("busy_start_s")
        prev_end = -1
        for r in g.itertuples():
            if r.busy_start_s < prev_end - 1e-9:
                fail(f"UAV conflict {uav}")
            prev_end = r.busy_end_s

    # battery conflicts + recharge 100%
    for bid, g in bat_cal.groupby("battery_id"):
        g = g.sort_values("takeoff_s")
        ready = 0.0
        for r in g.itertuples():
            if r.takeoff_s < ready - 1e-9:
                fail(f"battery conflict {bid}")
            srow = sorties[sorties.sortie_id == r.sortie_id].iloc[0]
            gtype = types.loc[srow.uav_type]
            soc = 1.0 - srow.energy_kwh / float(gtype.battery_energy_kwh)
            t_full = float(
                pd.read_csv(PROCESSED_DIR / "transport_batteries.csv")
                .set_index("uav_type")
                .loc[srow.uav_type, "full_charge_time_s"]
            )
            ready = r.return_s + charge_time_s(soc, t_full)

    # metrics
    makespan = float(delivery.groupby("sortie_id").delivery_time_s.max().max())  # placeholder
    makespan = float(sorties.return_s.max())
    energy = float(sorties.energy_kwh.sum())
    n_sorties = len(sorties)
    if abs(float(obj.makespan) - makespan) > 1e-6:
        fail("makespan metric")
    if abs(float(obj.energy) - energy) > 1e-6:
        fail("energy metric")
    if int(obj.sorties) != n_sorties:
        fail("sorties metric")

    hard_ok = bool(delivery.hard_deadline_ok.all()) if "hard_deadline_ok" in delivery else True
    if not hard_ok:
        fail("hard_deadline_ok flag")

    print("E3_Q2_VALID")


if __name__ == "__main__":
    main()
