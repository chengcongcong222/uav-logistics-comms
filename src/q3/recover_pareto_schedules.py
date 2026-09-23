"""Recover P01-P04 full schedules from real search, validate, write pareto_schedules/."""
from __future__ import annotations

import json
import shutil
import time
from pathlib import Path

import pandas as pd

from src.common.paths import EXPORT_DIR, RESULTS_Q2
from src.q2.alns import alns_search
from src.q2.evaluator import MissionEvaluator
from src.q2.evaluator_sol import evaluate_solution, pack_key
from src.q2.initial_solution import build_b0, build_b1
from src.q2.scheduler import ResourceDecoder
from src.q2.solve_q2 import dump_solution, load_tables, metrics_row
from src.q2.export_trace import build_trace

OUT = RESULTS_Q2 / "pareto_schedules"

# Target points from q2_pareto.csv (order P01..P04)
TARGETS = [
    ("P01", "stage1", 2026092302, "j_time", 80, None),
    ("P02", "eps", 2026092401, "sorties", 25, 0.0),
    ("P03", "eps", 2026092401, "makespan", 25, 0.01),
    ("P04", "eps", 2026092401, "sorties", 25, 0.01),
]


def dump_pareto_solution(sol, evaluator, pdir: Path, pareto_id: str, meta: dict) -> None:
    pdir.mkdir(parents=True, exist_ok=True)
    dump_solution(sol, pareto_id, evaluator)
    # copy tag files to standard names inside pdir
    for name in ("sorties", "box_delivery", "uav_calendar", "battery_calendar"):
        src = RESULTS_Q2 / f"q2_{name}_{pareto_id}.csv"
        shutil.copy(src, pdir / f"q2_{name}.csv")
    (pdir / "objectives.json").write_text(
        json.dumps({**{k: sol.metrics[k] for k in ("J_time", "makespan", "energy", "sorties")}, **meta},
                   indent=2),
        encoding="utf-8",
    )
    # write official-named files temporarily then trace
    for name in ("sorties", "box_delivery", "uav_calendar", "battery_calendar"):
        shutil.copy(RESULTS_Q2 / f"q2_{name}_{pareto_id}.csv", RESULTS_Q2 / f"q2_{name}.csv")
    # patch export_trace to read current q2_sorties.csv
    import src.q2.export_trace as et

    df = et.build_trace()
    df.to_csv(pdir / "transport_trace.csv", index=False)


def main() -> None:
    tables = load_tables()
    evaluator = MissionEvaluator(tables, rho=0.20)
    decoder = ResourceDecoder(tables, rho=0.20)
    b0 = build_b0(evaluator, decoder)
    b1 = build_b1(evaluator, decoder, b0)

    for pid, kind, seed, mode, iters, eps in TARGETS:
        print(f"=== recovering {pid} {kind} seed={seed} mode={mode} eps={eps} ===", flush=True)
        j_bound = None
        if kind == "eps":
            # stage1 best known from file
            s1 = pd.read_csv(RESULTS_Q2 / "alns_runs.csv")
            j_best = float(s1.J_time.min())
            j_bound = (1.0 + float(eps)) * j_best
        t0 = time.time()
        sol, log = alns_search(
            b1, evaluator, decoder, seed=seed, iterations=iters, mode=mode, j_bound=j_bound
        )
        rt = time.time() - t0
        meta = {"pareto_id": pid, "kind": kind, "seed": seed, "mode": mode, "iterations": iters, "eps": eps, "runtime_s": rt}
        dump_pareto_solution(sol, evaluator, OUT / pid, pid, meta)
        print(pid, sol.metrics, flush=True)

    print("E4_PARETO_SCHEDULES_READY", flush=True)


if __name__ == "__main__":
    main()
