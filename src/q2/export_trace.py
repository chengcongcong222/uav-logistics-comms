"""Export Q2 transport trajectory for Q3 / ns-3 (relay_id empty)."""
from __future__ import annotations

import pandas as pd

from src.common.paths import EXPORT_DIR, PROCESSED_DIR, RESULTS_Q2
from src.common.route_geometry import climb_descent_m
from src.common.schemas import SERVICE_OPERATION_AGL_M
from src.q2.solve_q2 import load_tables


def main() -> None:
    tables = load_tables()
    nodes = tables["nodes"].set_index("node_id")
    types = tables["types"]
    geom = tables["geom"].set_index(["from_id", "to_id"])
    sorties = pd.read_csv(RESULTS_Q2 / "q2_sorties.csv")
    rows = []

    def op_alt(nid: str) -> float:
        n = nodes.loc[nid]
        if n.node_type == "dispatch_center":
            return float(n.ground_elevation_m)
        return float(n.ground_elevation_m) + SERVICE_OPERATION_AGL_M

    for s in sorties.itertuples():
        t = types.loc[s.uav_type]
        seq = ["O01"] + str(s.service_sequence).split(">") + ["O01"]
        tcur = s.takeoff_s
        # climb-cruise-descent per leg (piecewise linear in time)
        for a, b in zip(seq[:-1], seq[1:]):
            row = geom.loc[(a, b)]
            climb = float(row.climb_height_m)
            desc = float(row.descent_height_m)
            dist = float(row.horizontal_distance_m)
            vc, vu, vd = float(t.cruise_speed_mps), float(t.max_climb_mps), float(t.max_descend_mps)
            ta, tb = op_alt(a), op_alt(b)
            cruise = float(row.planned_cruise_altitude_m)
            xa, ya = nodes.loc[a, "x_m"], nodes.loc[a, "y_m"]
            xb, yb = nodes.loc[b, "x_m"], nodes.loc[b, "y_m"]
            # climb
            if climb > 0:
                rows.append({"node_id": s.uav_id, "time": tcur, "x": xa, "y": ya, "z": ta, "mode": "climb", "task_id": s.sortie_id, "relay_id": ""})
                tcur += climb / vu
                rows.append({"node_id": s.uav_id, "time": tcur, "x": xa, "y": ya, "z": cruise, "mode": "climb", "task_id": s.sortie_id, "relay_id": ""})
            # cruise
            rows.append({"node_id": s.uav_id, "time": tcur, "x": xa, "y": ya, "z": cruise, "mode": "cruise", "task_id": s.sortie_id, "relay_id": ""})
            tcur += dist / vc
            rows.append({"node_id": s.uav_id, "time": tcur, "x": xb, "y": yb, "z": cruise, "mode": "cruise", "task_id": s.sortie_id, "relay_id": ""})
            # descent
            if desc > 0:
                tcur += desc / vd
                rows.append({"node_id": s.uav_id, "time": tcur, "x": xb, "y": yb, "z": tb, "mode": "descent", "task_id": s.sortie_id, "relay_id": ""})
            if b != "O01":
                # handover window
                rows.append({"node_id": s.uav_id, "time": tcur, "x": xb, "y": yb, "z": tb, "mode": "handover", "task_id": s.sortie_id, "relay_id": ""})
                # approximate handover duration from delivery time difference is implicit; use type params
                # delivery already computed in schedule; keep a short stamp at delivery time
                # find delivery
                # fall through
            else:
                rows.append({"node_id": s.uav_id, "time": s.return_s, "x": xa, "y": ya, "z": ta, "mode": "return", "task_id": s.sortie_id, "relay_id": ""})
                tcur = s.return_s
        # prepend prep
        rows.insert(0, {"node_id": s.uav_id, "time": s.preparation_start_s, "x": nodes.loc["O01", "x_m"], "y": nodes.loc["O01", "y_m"], "z": nodes.loc["O01", "ground_elevation_m"], "mode": "prep", "task_id": s.sortie_id, "relay_id": ""})

    df = pd.DataFrame(rows, columns=["node_id", "time", "x", "y", "z", "mode", "task_id", "relay_id"])
    df = df.sort_values(["node_id", "time"]).reset_index(drop=True)
    out = EXPORT_DIR / "q2_transport_trace.csv"
    df.to_csv(out, index=False)
    print(f"wrote {out} rows={len(df)}")


if __name__ == "__main__":
    main()
