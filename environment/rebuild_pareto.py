#!/usr/bin/env python3
from pathlib import Path
import sys
ROOT = Path("/home/ccc/projects/uav-logistics-comms")
sys.path.insert(0, str(ROOT))
import pandas as pd
from src.q2.solve_q2 import load_tables, metrics_row, nondominated, OBJ_KEYS
from src.q2.evaluator import MissionEvaluator
from src.q2.evaluator_sol import evaluate_solution
from src.q2.initial_solution import pack_key
from src.q2.scheduler import ResourceDecoder

tables = load_tables()
ev = MissionEvaluator(tables, 0.2)
dec = ResourceDecoder(tables, 0.2)

def load_raw(tag):
    sorties = pd.read_csv(f"results/q2/q2_sorties_{tag}.csv")
    delivery = pd.read_csv(f"results/q2/q2_box_delivery_{tag}.csv")
    raw = []
    for s in sorties.itertuples():
        by = delivery[delivery.sortie_id == s.sortie_id].groupby("service_id").box_id.apply(list).to_dict()
        raw.append(pack_key(s.uav_type, str(s.service_sequence).split(">"), by))
    return evaluate_solution(raw, ev, dec)

b0, b1 = load_raw("B0"), load_raw("B1")
s1 = pd.read_csv("results/q2/alns_runs.csv")
eps = pd.read_csv("results/q2/q2_epsilon_solutions.csv")
rows = [metrics_row(b0, "B0"), metrics_row(b1, "B1")]
for r in s1.to_dict("records"):
    rows.append({"source": "stage1_seed", "seed": r["seed"], **{k: r[k] for k in OBJ_KEYS}})
rows.extend(eps.to_dict("records"))
p = nondominated(rows)
p.to_csv("results/q2/q2_pareto.csv", index=False)
print(p[["source", "J_time", "makespan", "energy", "sorties"]].to_string(index=False))
print("pareto", len(p))
