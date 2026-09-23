#!/usr/bin/env python3
print("start", flush=True)
from pathlib import Path
import sys
sys.path.insert(0, "/home/ccc/projects/uav-logistics-comms")
print("importing", flush=True)
from src.q2.solve_q2 import load_tables
from src.q2.evaluator import MissionEvaluator
from src.q2.scheduler import ResourceDecoder
from src.q2.evaluator_sol import evaluate_solution
from src.q3.recover_eps_points import load_raw
print("loaded modules", flush=True)
tables = load_tables()
ev = MissionEvaluator(tables, 0.2)
dec = ResourceDecoder(tables, 0.2)
raw = load_raw("B1")
print("raw", len(raw), flush=True)
sol = evaluate_solution(raw, ev, dec)
print("sol", sol.metrics if sol else None, flush=True)
