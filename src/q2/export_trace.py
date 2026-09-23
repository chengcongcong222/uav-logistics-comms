"""Export Q2 transport trajectory for Q3 / ns-3 (relay_id empty).

Each flight phase is emitted as two waypoints with the same `mode`:
  mode start (t0, pos0) -> mode end (t1, pos1), duration = t1-t0 = phase time.
Handover is an interval at the service point: handover_start / handover_end.
Return ends at O01 ground at sortie.return_s.
"""
from __future__ import annotations

import pandas as pd

from src.common.paths import EXPORT_DIR, RESULTS_Q2
from src.common.schemas import SERVICE_OPERATION_AGL_M
from src.q2.solve_q2 import load_tables


def op_alt(nodes, nid: str) -> float:
    n = nodes.loc[nid]
    if n.node_type == "dispatch_center":
        return float(n.ground_elevation_m)
    return float(n.ground_elevation_m) + SERVICE_OPERATION_AGL_M


def build_trace() -> pd.DataFrame:
    tables = load_tables()
    nodes = tables["nodes"].set_index("node_id")
    types = tables["types"]
    geom = tables["geom"].set_index(["from_id", "to_id"])
    sorties = pd.read_csv(RESULTS_Q2 / "q2_sorties.csv")
    delivery = pd.read_csv(RESULTS_Q2 / "q2_box_delivery.csv")
    rows: list[dict] = []

    def add(uav, t, x, y, z, mode, task, phase_role=""):
        rows.append(
            {
                "node_id": uav,
                "time": float(t),
                "x": float(x),
                "y": float(y),
                "z": float(z),
                "mode": mode,
                "task_id": task,
                "relay_id": "",
                "phase_role": phase_role,
            }
        )

    for s in sorties.itertuples():
        t = types.loc[s.uav_type]
        seq = ["O01"] + str(s.service_sequence).split(">") + ["O01"]
        n_by = (
            delivery[delivery.sortie_id == s.sortie_id]
            .groupby("service_id")
            .box_id.count()
            .to_dict()
        )
        x01, y01 = float(nodes.loc["O01", "x_m"]), float(nodes.loc["O01", "y_m"])
        z01 = op_alt(nodes, "O01")

        add(s.uav_id, s.preparation_start_s, x01, y01, z01, "prep", s.sortie_id, "start")
        add(s.uav_id, s.takeoff_s, x01, y01, z01, "prep", s.sortie_id, "end")
        add(s.uav_id, s.takeoff_s, x01, y01, z01, "takeoff", s.sortie_id, "instant")
        tcur = float(s.takeoff_s)

        for a, b in zip(seq[:-1], seq[1:]):
            row = geom.loc[(a, b)]
            climb = float(row.climb_height_m)
            desc = float(row.descent_height_m)
            dist = float(row.horizontal_distance_m)
            vc = float(t.cruise_speed_mps)
            vu = float(t.max_climb_mps)
            vd = float(t.max_descend_mps)
            ta, tb = op_alt(nodes, a), op_alt(nodes, b)
            cruise = float(row.planned_cruise_altitude_m)
            xa, ya = float(nodes.loc[a, "x_m"]), float(nodes.loc[a, "y_m"])
            xb, yb = float(nodes.loc[b, "x_m"]), float(nodes.loc[b, "y_m"])

            # climb: (xa,ya,ta) -> (xa,ya,cruise)
            add(s.uav_id, tcur, xa, ya, ta, "climb", s.sortie_id, "start")
            tcur += climb / vu if climb > 0 else 0.0
            add(s.uav_id, tcur, xa, ya, cruise, "climb", s.sortie_id, "end")

            # cruise: (xa,ya,cruise) -> (xb,yb,cruise)
            add(s.uav_id, tcur, xa, ya, cruise, "cruise", s.sortie_id, "start")
            tcur += dist / vc
            add(s.uav_id, tcur, xb, yb, cruise, "cruise", s.sortie_id, "end")

            # descent: (xb,yb,cruise) -> (xb,yb,tb)
            add(s.uav_id, tcur, xb, yb, cruise, "descent", s.sortie_id, "start")
            tcur += desc / vd if desc > 0 else 0.0
            add(s.uav_id, tcur, xb, yb, tb, "descent", s.sortie_id, "end")

            if b == "O01":
                add(s.uav_id, tcur, x01, y01, z01, "return", s.sortie_id, "instant")
            else:
                n_boxes = int(n_by.get(b, 0))
                t_hand = float(t.handover_base_s) + n_boxes * float(t.handover_per_box_s)
                add(s.uav_id, tcur, xb, yb, tb, "handover_start", s.sortie_id, "start")
                tcur += t_hand
                add(s.uav_id, tcur, xb, yb, tb, "handover_end", s.sortie_id, "end")

        if abs(tcur - float(s.return_s)) > 1e-3:
            raise RuntimeError(
                f"trace return mismatch {s.sortie_id}: t_trace={tcur} return_s={s.return_s}"
            )

    df = pd.DataFrame(
        rows,
        columns=[
            "node_id",
            "time",
            "x",
            "y",
            "z",
            "mode",
            "task_id",
            "relay_id",
            "phase_role",
        ],
    )
    df = df.sort_values(["task_id", "time", "mode", "phase_role"], kind="mergesort").reset_index(
        drop=True
    )
    return df


def main() -> None:
    df = build_trace()
    out = EXPORT_DIR / "q2_transport_trace.csv"
    df.to_csv(out, index=False)
    print(f"wrote {out} rows={len(df)}")


if __name__ == "__main__":
    main()
