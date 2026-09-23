#!/usr/bin/env python3
print("A", flush=True)
import sys
sys.path.insert(0, "/home/ccc/projects/uav-logistics-comms")
from src.q2.solve_q2 import load_tables
from src.q2.evaluator import MissionEvaluator
from src.q2.scheduler import ResourceDecoder
from src.q2.evaluator_sol import evaluate_solution
from src.q2.alns import alns_search
from src.q3.recover_eps_points import load_raw
print("B", flush=True)
tables = load_tables()
ev = MissionEvaluator(tables, 0.2)
dec = ResourceDecoder(tables, 0.2)
b1 = evaluate_solution(load_raw("B1"), ev, dec)
print("C start alns", flush=True)
sol, log = alns_search(b1, ev, dec, seed=2026092401, iterations=8, mode="sorties", j_bound=0.478)
print("D", sol.metrics, flush=True)
