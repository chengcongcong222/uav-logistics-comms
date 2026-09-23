"""Q1: max safe payload + no-cross-service batching + reserve sensitivity (optimized DP)."""
from __future__ import annotations

import pandas as pd

from src.common.flight_time import handover_time_s, leg_flight_time_s, load_time_s
from src.common.margins import DEFAULT_RHO, RHO_GRID
from src.common.paths import PROCESSED_DIR, RESULTS_Q1
from src.common.transport_energy import leg_energy_kwh, return_reserve_ok


def load_tables():
    types = pd.read_csv(PROCESSED_DIR / "transport_uav_types.csv").set_index("uav_type")
    nodes = pd.read_csv(PROCESSED_DIR / "nodes.csv").set_index("node_id")
    geom = pd.read_csv(PROCESSED_DIR / "route_geometry.csv")
    boxes = pd.read_csv(PROCESSED_DIR / "boxes.csv")
    return types, nodes, geom, boxes


def leg_params(geom: pd.DataFrame, i: str, j: str) -> pd.Series:
    row = geom[(geom.from_id == i) & (geom.to_id == j)]
    if row.empty:
        raise KeyError(f"missing leg {i}->{j}")
    return row.iloc[0]


def roundtrip_energy(types, geom, g: str, service: str, q: float) -> float:
    t = types.loc[g]
    e_use = float(t.battery_energy_kwh)
    out = leg_params(geom, "O01", service)
    back = leg_params(geom, service, "O01")
    e1 = leg_energy_kwh(
        out.horizontal_distance_m,
        out.climb_height_m,
        out.descent_height_m,
        q,
        t.empty_mass_with_battery_kg,
        t.range_empty_m,
        t.range_full_m,
        t.max_payload_kg,
        e_use,
        t.climb_energy_eff,
        t.descend_energy_eff,
    )
    e2 = leg_energy_kwh(
        back.horizontal_distance_m,
        back.climb_height_m,
        back.descent_height_m,
        0.0,
        t.empty_mass_with_battery_kg,
        t.range_empty_m,
        t.range_full_m,
        t.max_payload_kg,
        e_use,
        t.climb_energy_eff,
        t.descend_energy_eff,
    )
    return e1 + e2


def max_safe_payload(types, geom, g: str, service: str, rho: float) -> dict:
    t = types.loc[g]
    q_mass = float(t.max_payload_kg)
    e_use = float(t.battery_energy_kwh)
    e0 = roundtrip_energy(types, geom, g, service, 0.0)
    if not return_reserve_ok(e0, e_use, rho):
        return {
            "uav_type": g,
            "service_id": service,
            "payload_limit_kg": 0.0,
            "binding_constraint": "energy_infeasible_even_empty",
            "roundtrip_energy_kwh": e0,
            "energy_margin_kwh": (1 - rho) * e_use - e0,
            "return_soc": 1.0 - e0 / e_use,
        }
    if return_reserve_ok(roundtrip_energy(types, geom, g, service, q_mass), e_use, rho):
        q_max = q_mass
        binding = "mass"
    else:
        lo, hi = 0.0, q_mass
        for _ in range(50):
            mid = 0.5 * (lo + hi)
            if return_reserve_ok(roundtrip_energy(types, geom, g, service, mid), e_use, rho):
                lo = mid
            else:
                hi = mid
        q_max = lo
        binding = "energy"
    e = roundtrip_energy(types, geom, g, service, q_max)
    return {
        "uav_type": g,
        "service_id": service,
        "payload_limit_kg": q_max,
        "binding_constraint": binding,
        "roundtrip_energy_kwh": e,
        "energy_margin_kwh": (1 - rho) * e_use - e,
        "return_soc": 1.0 - e / e_use,
    }


def flight_cost(types, geom, g: str, service: str, n_boxes: int, mass: float, volume: float, rho: float):
    t = types.loc[g]
    if mass > float(t.max_payload_kg) + 1e-9 or volume > float(t.cargo_volume_m3) + 1e-9:
        return None
    e = roundtrip_energy(types, geom, g, service, mass)
    e_use = float(t.battery_energy_kwh)
    if not return_reserve_ok(e, e_use, rho):
        return None
    out = leg_params(geom, "O01", service)
    back = leg_params(geom, service, "O01")
    t_out = leg_flight_time_s(
        out.climb_height_m,
        out.horizontal_distance_m,
        out.descent_height_m,
        t.max_climb_mps,
        t.cruise_speed_mps,
        t.max_descend_mps,
    )
    t_back = leg_flight_time_s(
        back.climb_height_m,
        back.horizontal_distance_m,
        back.descent_height_m,
        t.max_climb_mps,
        t.cruise_speed_mps,
        t.max_descend_mps,
    )
    t_total = (
        float(t.prep_time_s)
        + load_time_s(n_boxes, float(t.load_time_per_box_s))
        + t_out
        + handover_time_s(n_boxes, float(t.handover_base_s), float(t.handover_per_box_s))
        + t_back
    )
    return (e, t_total, g, mass, volume, n_boxes)


def pack_service(types, geom, service: str, boxes: pd.DataFrame, rho: float) -> list[dict]:
    items = boxes[boxes.service_id == service].reset_index(drop=True)
    n = len(items)
    if n == 0:
        return []
    masses = items.mass_kg.to_numpy()
    volumes = items.volume_m3.to_numpy()
    # precompute best flight for every subset
    best_flight = [None] * (1 << n)
    for mask in range(1, 1 << n):
        m = v = 0.0
        nb = 0
        for i in range(n):
            if mask & (1 << i):
                m += masses[i]
                v += volumes[i]
                nb += 1
        local = None
        for g in types.index:
            c = flight_cost(types, geom, g, service, nb, m, v, rho)
            if c is None:
                continue
            key = (c[0], c[1], c[2])  # energy, time, type
            if local is None or key < local[0]:
                local = (key, c)
        best_flight[mask] = local

    # set partition DP
    INF = (0, float("inf"), float("inf"), [])
    best = {0: (0, 0.0, 0.0, [])}
    full = (1 << n) - 1
    for mask in range(1, full + 1):
        # only expand submasks containing lowest set bit
        low = mask & (-mask)
        sub = mask
        while sub:
            if sub & low and best_flight[sub] is not None:
                rest = mask ^ sub
                if rest in best:
                    nf, en, tm, asg = best[rest]
                    key, c = best_flight[sub]
                    cand = (nf + 1, en + key[0], tm + key[1], asg + [(c[2], sub, c)])
                    if mask not in best or cand[:3] < best[mask][:3]:
                        best[mask] = cand
            sub = (sub - 1) & mask
    if full not in best:
        raise RuntimeError(f"Q1 packing infeasible for {service}")
    nf, en, tm, asg = best[full]
    flights = []
    for g, submask, c in asg:
        ids = [items.box_id.iloc[i] for i in range(n) if submask & (1 << i)]
        flights.append(
            {
                "service_id": service,
                "uav_type": g,
                "box_ids": ids,
                "n_boxes": c[5],
                "mass_kg": c[3],
                "volume_m3": c[4],
                "energy_kwh": c[0],
                "time_s": c[1],
            }
        )
    return flights


def solve_q1(types, geom, boxes, rho: float) -> pd.DataFrame:
    rows = []
    for service in sorted(boxes.service_id.unique()):
        for f in pack_service(types, geom, service, boxes, rho):
            rows.append({**f, "rho": rho})
    return pd.DataFrame(rows)


def main() -> None:
    types, nodes, geom, boxes = load_tables()
    rows = [max_safe_payload(types, geom, g, s, DEFAULT_RHO) for g in types.index for s in sorted(boxes.service_id.unique())]
    pd.DataFrame(rows).to_csv(RESULTS_Q1 / "max_safe_payload.csv", index=False)

    fl = solve_q1(types, geom, boxes, DEFAULT_RHO)
    fl.to_csv(RESULTS_Q1 / "q1_packings_rho20.csv", index=False)

    sens_rows = []
    for rho in RHO_GRID:
        for g in types.index:
            for service in sorted(boxes.service_id.unique()):
                mp = max_safe_payload(types, geom, g, service, rho)
                sens_rows.append({"rho": rho, "kind": "max_payload", **mp})
        fl_r = solve_q1(types, geom, boxes, rho)
        sens_rows.append(
            {
                "rho": rho,
                "kind": "packing_summary",
                "n_flights": len(fl_r),
                "total_energy_kwh": float(fl_r.energy_kwh.sum()),
                "total_time_s": float(fl_r.time_s.sum()),
            }
        )
    pd.DataFrame(sens_rows).to_csv(RESULTS_Q1 / "reserve_sensitivity.csv", index=False)
    print(f"q1_flights={len(fl)} total_energy={fl.energy_kwh.sum():.4f} total_time={fl.time_s.sum():.1f}")
    print("Q1_SOLVED")


if __name__ == "__main__":
    main()
