"""Recover epsilon Pareto points P02-P04 with original warm-start chain + dump."""
from __future__ import annotations

import json
import shutil
import time
from pathlib import Path

import pandas as pd

from src.q2.alns import alns_search
from src.q2.evaluator import MissionEvaluator
from src.q2.initial_solution import build_b0, build_b1
from src.q2.scheduler import ResourceDecoder
from src.q2.solve_q2 import dump_solution, load_tables
from src.q2.export_trace import build_trace

OUT = Path("/home/ccc/projects/uav-logistics-comms/results/q2/pareto_schedules")
RESULTS_Q2 = Path("/home/ccc/projects/uav-logistics-comms/results/q2")


def save(sol, evaluator, pid, meta):
    pdir = OUT / pid
    pdir.mkdir(parents=True, exist_ok=True)
    dump_solution(sol, pid, evaluator)
    for name in ("sorties", "box_delivery", "uav_calendar", "battery_calendar"):
        shutil.copy(RESULTS_Q2 / f"q2_{name}_{pid}.csv", pdir / f"q2_{name}.csv")
        shutil.copy(RESULTS_Q2 / f"q2_{name}_{pid}.csv", RESULTS_Q2 / f"q2_{name}.csv")
    (pdir / "objectives.json").write_text(
        json.dumps({"metrics": {k: sol.metrics[k] for k in ("J_time", "makespan", "energy", "sorties")}, **meta}, indent=2),
        encoding="utf-8",
    )
    # also save raw mission structure for reproducibility
    (pdir / "missions.json").write_text(json.dumps(sol.missions, ensure_ascii=False, indent=2), encoding="utf-8")
    print("saved files", pid, flush=True)
    try:
        tr = build_trace()
        tr.to_csv(pdir / "transport_trace.csv", index=False)
        print("trace ok", pid, len(tr), flush=True)
    except Exception as e:  # noqa: BLE001
        print("trace failed", pid, e, flush=True)
    print("saved", pid, sol.metrics, flush=True)


def load_raw(tag: str):
    sorties = pd.read_csv(RESULTS_Q2 / f"q2_sorties_{tag}.csv")
    delivery = pd.read_csv(RESULTS_Q2 / f"q2_box_delivery_{tag}.csv")
    from src.q2.initial_solution import pack_key

    raw = []
    for s in sorties.itertuples():
        by = (
            delivery[delivery.sortie_id == s.sortie_id]
            .groupby("service_id")
            .box_id.apply(list)
            .to_dict()
        )
        raw.append(pack_key(s.uav_type, str(s.service_sequence).split(">"), by))
    return raw


def main() -> None:
    print("EPS_RECOVER_START", flush=True)
    tables = load_tables()
    ev = MissionEvaluator(tables, 0.2)
    dec = ResourceDecoder(tables, 0.2)
    from src.q2.evaluator_sol import evaluate_solution

    b0 = evaluate_solution(load_raw("B0"), ev, dec)
    b1 = evaluate_solution(load_raw("B1"), ev, dec)
    assert b0 and b1
    print("BASELINES_OK", b1.metrics, flush=True)
    s1 = pd.read_csv(RESULTS_Q2 / "alns_runs.csv")
    j_best = float(s1.J_time.min())

    # warm-start chain like original stage2 (seed 2026092401 first, then 2026092402)
    incumbent = None
    found = []
    for eps, obj_mode, pid in [
        (0.0, "sorties", "P02"),
        (0.0, "makespan", "P02b"),
        (0.0, "energy", "P02c"),
        (0.01, "makespan", "P03"),
        (0.01, "energy", "P03b"),
        (0.01, "sorties", "P04"),
        (0.02, "makespan", "P03c"),
        (0.02, "sorties", "P04b"),
        (0.05, "energy", "P05e"),
        (0.05, "sorties", "P05s"),
    ]:
        bound = (1.0 + eps) * j_best
        start = incumbent if (incumbent and incumbent.metrics["J_time"] <= bound + 1e-9) else b1
        sub_best = None
        for seed in (2026092401, 2026092402):
            sol, _ = alns_search(start, ev, dec, seed=seed, iterations=8, mode=obj_mode, j_bound=bound)
            if sol.metrics["J_time"] <= bound + 1e-9:
                if sub_best is None:
                    sub_best = sol
                else:
                    from src.q2.alns import score_tuple

                    if score_tuple(sol, obj_mode) < score_tuple(sub_best, obj_mode):
                        sub_best = sol
        if sub_best is None:
            continue
        if incumbent is None:
            incumbent = sub_best
        found.append((pid, eps, obj_mode, sub_best))
        save(sub_best, ev, pid, {"eps": eps, "mode": obj_mode, "j_bound": bound})
        # keep lowest J_time as incumbent
        from src.q2.alns import score_tuple

        if score_tuple(sub_best, "j_time") < score_tuple(incumbent, "j_time"):
            incumbent = sub_best

    # pick three diverse points as P02/P03/P04 if needed
    print("FOUND", len(found), flush=True)
    for pid, eps, mode, sol in found:
        print(pid, mode, sol.metrics, flush=True)


if __name__ == "__main__":
    main()
