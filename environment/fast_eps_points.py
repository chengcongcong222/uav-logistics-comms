#!/usr/bin/env python3
"""Minimal P02-P04 recovery: 3 real ALNS runs + full dump + trace."""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, "/home/ccc/projects/uav-logistics-comms")

from src.q2.alns import alns_search
from src.q2.evaluator import MissionEvaluator
from src.q2.evaluator_sol import evaluate_solution, pack_key
from src.q2.scheduler import ResourceDecoder
from src.q2.solve_q2 import dump_solution, load_tables
from src.q2.export_trace import build_trace
import pandas as pd

ROOT = Path("/home/ccc/projects/uav-logistics-comms")
RESULTS_Q2 = ROOT / "results/q2"
OUT = RESULTS_Q2 / "pareto_schedules"


def load_raw(tag: str):
    sorties = pd.read_csv(RESULTS_Q2 / f"q2_sorties_{tag}.csv")
    delivery = pd.read_csv(RESULTS_Q2 / f"q2_box_delivery_{tag}.csv")
    raw = []
    for s in sorties.itertuples():
        by = delivery[delivery.sortie_id == s.sortie_id].groupby("service_id").box_id.apply(list).to_dict()
        raw.append(pack_key(s.uav_type, str(s.service_sequence).split(">"), by))
    return raw


def save(sol, ev, pid, meta):
    pdir = OUT / pid
    pdir.mkdir(parents=True, exist_ok=True)
    dump_solution(sol, pid, ev)
    for name in ("sorties", "box_delivery", "uav_calendar", "battery_calendar"):
        shutil.copy(RESULTS_Q2 / f"q2_{name}_{pid}.csv", pdir / f"q2_{name}.csv")
        shutil.copy(RESULTS_Q2 / f"q2_{name}_{pid}.csv", RESULTS_Q2 / f"q2_{name}.csv")
    (pdir / "objectives.json").write_text(
        json.dumps({"metrics": {k: sol.metrics[k] for k in ("J_time", "makespan", "energy", "sorties")}, **meta}, indent=2),
        encoding="utf-8",
    )
    (pdir / "missions.json").write_text(json.dumps(sol.missions, ensure_ascii=False, indent=2), encoding="utf-8")
    tr = build_trace()
    tr.to_csv(pdir / "transport_trace.csv", index=False)
    print("SAVED", pid, sol.metrics, flush=True)


def main() -> None:
    tables = load_tables()
    ev = MissionEvaluator(tables, 0.2)
    dec = ResourceDecoder(tables, 0.2)
    b1 = evaluate_solution(load_raw("B1"), ev, dec)
    jobs = [
        ("P02", 2026092401, "sorties", 0.0),
        ("P03", 2026092401, "makespan", 0.01),
        ("P04", 2026092402, "sorties", 0.01),
    ]
    s1 = pd.read_csv(RESULTS_Q2 / "alns_runs.csv")
    j_best = float(s1.J_time.min())
    for pid, seed, mode, eps in jobs:
        bound = (1.0 + eps) * j_best
        print("RUN", pid, seed, mode, bound, flush=True)
        sol, _ = alns_search(b1, ev, dec, seed=seed, iterations=8, mode=mode, j_bound=bound)
        save(sol, ev, pid, {"seed": seed, "mode": mode, "eps": eps, "j_bound": bound})
    print("E4_EPS_POINTS_READY", flush=True)


if __name__ == "__main__":
    main()
