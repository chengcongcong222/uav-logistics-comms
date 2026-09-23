"""Deterministic UAV + battery resource decoder (not encoded in ALNS)."""
from __future__ import annotations

from dataclasses import dataclass, field

from src.common.charging import charge_time_s
from src.q2.mission import Mission


@dataclass
class ResourceState:
    uav_busy_until: dict[str, float] = field(default_factory=dict)
    batt_ready_at: dict[str, float] = field(default_factory=dict)
    uav_type: dict[str, str] = field(default_factory=dict)
    batt_type: dict[str, str] = field(default_factory=dict)
    batt_soc_at_return: dict[str, float] = field(default_factory=dict)


class ResourceDecoder:
    def __init__(self, tables: dict, rho: float = 0.20):
        self.types = tables["types"]
        self.uavs = tables["uavs"]
        self.batteries = tables["batteries"]
        self.rho = rho
        self.e_use = {g: float(self.types.loc[g, "battery_energy_kwh"]) for g in self.types.index}
        self.t_full = {
            r.uav_type: float(r.full_charge_time_s) for r in self.batteries.itertuples()
        }
        self.pool = {
            r.uav_type: int(r.battery_pool_count) for r in self.batteries.itertuples()
        }
        self.batt_ids = {
            g: [f"BAT-{g}-{i+1:02d}" for i in range(n)] for g, n in self.pool.items()
        }

    def init_state(self) -> ResourceState:
        st = ResourceState()
        for r in self.uavs.itertuples():
            st.uav_busy_until[r.uav_id] = 0.0
            st.uav_type[r.uav_id] = r.uav_type
        for g, ids in self.batt_ids.items():
            for bid in ids:
                st.batt_ready_at[bid] = 0.0
                st.batt_type[bid] = g
        return st

    def _plan(self, m: Mission, st: ResourceState, uav: str, bid: str):
        g = m.uav_type
        prep_load = float(m.relative_takeoff_time)  # prep+load duration
        flight_service = float(m.relative_return_time) - float(m.relative_takeoff_time)
        uav_free = st.uav_busy_until[uav]
        batt_ready = st.batt_ready_at[bid]

        def times_for(prep_start: float):
            nominal_to = prep_start + prep_load
            takeoff = max(nominal_to, batt_ready)
            wait = takeoff - nominal_to
            ret = takeoff + flight_service
            deliv = {s: prep_start + wait + dt for s, dt in m.relative_delivery_times.items()}
            return prep_start, takeoff, ret, deliv, wait

        # earliest feasible prep_start in [uav_free, latest]
        latest = m.hard_deadline_latest_start
        lo = uav_free
        hi = latest if latest is not None else lo
        if latest is not None and hi < lo:
            return None
        # if no hard constraint, earliest start
        if latest is None:
            prep_start = lo
            p, to, ret, deliv, wait = times_for(prep_start)
            return p, to, ret, deliv, wait
        # need prep_start + wait(prep_start) <= latest
        # try earliest; if wait pushes past latest, try starting later so prep overlaps charge
        # binary-ish search: also try prep_start = max(lo, batt_ready - prep_load)
        candidates = [lo, max(lo, batt_ready - prep_load), hi]
        # sample a few points
        for k in range(1, 6):
            candidates.append(lo + (hi - lo) * k / 6)
        best = None
        for ps in sorted(set(candidates)):
            if ps < lo - 1e-12 or ps > hi + 1e-12:
                continue
            p, to, ret, deliv, wait = times_for(ps)
            # hard: delivery abs = p + wait + rel = p + (to - (p+prep_load)) + rel = to - prep_load + rel
            ok = True
            for s, dt in m.relative_delivery_times.items():
                abs_td = to - prep_load + dt  # equals p + wait + dt
                # use latest as bound on prep_start; more precisely abs_td must be <= hard
                # hard_s = latest + rel_delivery_s for tightest; recompute via latest + dt
                if abs_td > (latest + dt) + 1e-9:
                    ok = False
                    break
            if ok and p <= latest + 1e-9:
                cand = (ret, to, p, deliv)
                if best is None or cand[0] < best[0]:
                    best = cand
        if best is None:
            return None
        ret, to, p, deliv = best
        wait = to - (p + prep_load)
        return p, to, ret, deliv, wait

    def decode_order(
        self, missions: list[Mission], state: ResourceState | None = None
    ) -> tuple[list[Mission], ResourceState, bool]:
        st = state if state is not None else self.init_state()
        out: list[Mission] = []
        for m in missions:
            g = m.uav_type
            options = []
            for uav in self.uavs[self.uavs.uav_type == g].uav_id:
                for bid in self.batt_ids[g]:
                    plan = self._plan(m, st, uav, bid)
                    if plan is None:
                        continue
                    p, to, ret, deliv, wait = plan
                    batt_recovery = ret + charge_time_s(
                        max(0.0, 1.0 - m.energy_kwh / self.e_use[g]), self.t_full[g]
                    )
                    options.append(
                        (ret, batt_recovery, bid, uav, p, to, ret, deliv)
                    )
            if not options:
                return out, st, False
            options.sort(key=lambda x: (x[0], x[1], x[2], x[3]))
            ret, batt_recovery, bid, uav, p, to, _r, deliv = options[0]
            m2 = Mission(
                mission_id=m.mission_id or f"M{len(out)+1:03d}",
                uav_type=g,
                box_ids=list(m.box_ids),
                service_sequence=list(m.service_sequence),
                boxes_by_service={k: list(v) for k, v in m.boxes_by_service.items()},
                initial_payload_kg=m.initial_payload_kg,
                initial_volume_m3=m.initial_volume_m3,
                relative_prep_start=0.0,
                relative_takeoff_time=m.relative_takeoff_time,
                relative_delivery_times=dict(m.relative_delivery_times),
                relative_return_time=m.relative_return_time,
                energy_kwh=m.energy_kwh,
                energy_margin_kwh=m.energy_margin_kwh,
                hard_deadline_latest_start=m.hard_deadline_latest_start,
                uav_id=uav,
                battery_id=bid,
                preparation_start_s=p,
                takeoff_s=to,
                return_s=ret,
                delivery_times_s=deliv,
            )
            st.uav_busy_until[uav] = ret
            st.batt_ready_at[bid] = batt_recovery
            st.batt_soc_at_return[bid] = 1.0 - m.energy_kwh / self.e_use[g]
            out.append(m2)
        return out, st, True
