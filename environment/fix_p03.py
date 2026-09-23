#!/usr/bin/env python3
import sys
sys.path.insert(0, "/home/ccc/projects/uav-logistics-comms")
import shutil
import json
from pathlib import Path
import pandas as pd
from src.q2.alns import alns_search
from src.q2.evaluator import MissionEvaluator
from src.q2.evaluator_sol import evaluate_solution, pack_key
from src.q2.scheduler import ResourceDecoder
from src.q2.solve_q2 import dump_solution, load_tables
from src.q2.export_trace import build_trace

ROOT = Path("/home/ccc/projects/uav-logistics-comms")
RESULTS_Q2 = ROOT / "results/q2"
OUT = RESULTS_Q2 / "pareto_schedules"


def load_raw(tag):
    sorties = pd.read_csv(RESULTS_Q2 / f"q2_sorties_{tag}.csv")
    delivery = pd.read_csv(RESULTS_Q2 / f"q2_box_delivery_{tag}.csv")
    raw = []
    for s in sorties.itertuples():
        by = delivery[delivery.sortie_id == s.sortie_id].groupby("service_id").box_id.apply(list).to_dict()
        raw.append(pack_key(s.uav_type, str(s.service_sequence).split(">"), by))
    return raw


tables = load_tables()
ev = MissionEvaluator(tables, 0.2)
dec = ResourceDecoder(tables, 0.2)
b1 = evaluate_solution(load_raw("B1"), ev, dec)
s1 = pd.read_csv(RESULTS_Q2 / "alns_runs.csv")
bound = 1.01 * float(s1.J_time.min())
print("P03 alt", bound, flush=True)
sol, _ = alns_search(b1, ev, dec, seed=2026092305, iterations=10, mode="makespan", j_bound=bound)
pid = "P03"
pdir = OUT / pid
pdir.mkdir(parents=True, exist_ok=True)
dump_solution(sol, pid, ev)
for name in ("sorties", "box_delivery", "uav_calendar", "battery_calendar"):
    shutil.copy(RESULTS_Q2 / f"q2_{name}_{pid}.csv", pdir / f"q2_{name}.csv")
    shutil.copy(RESULTS_Q2 / f"q2_{name}_{pid}.csv", RESULTS_Q2 / f"q2_{name}.csv")
(pdir / "objectives.json").write_text(json.dumps({"metrics": {k: sol.metrics[k] for k in ("J_time","makespan","energy","sorties")}, "seed": 2026092305, "mode": "makespan", "eps": 0.01}, indent=2))
(pdir / "missions.json").write_text(json.dumps(sol.missions, ensure_ascii=False, indent=2))
build_trace().to_csv(pdir / "transport_trace.csv", index=False)
print("SAVED P03", sol.metrics, flush=True)
