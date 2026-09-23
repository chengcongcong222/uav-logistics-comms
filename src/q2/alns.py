"""ALNS with simulated-annealing acceptance (searcher only)."""
from __future__ import annotations

import copy
import math
import random
import time
from dataclasses import dataclass, field

from src.q2.evaluator import GateStats, MissionEvaluator
from src.q2.evaluator_sol import Solution, evaluate_solution
from src.q2.operators import DESTROY, LOCAL, REPAIR
from src.q2.scheduler import ResourceDecoder

# primary objective keys for multi-objective subproblems
OBJ_KEYS = ("J_time", "makespan", "energy", "sorties")


@dataclass
class AlnsLog:
    seed: int = 0
    iterations: int = 0
    accepted_moves: int = 0
    improved_moves: int = 0
    runtime_s: float = 0.0
    best_trajectory: list[float] = field(default_factory=list)
    operator_scores: dict = field(default_factory=dict)
    operator_usage: dict = field(default_factory=dict)
    operator_accepted: dict = field(default_factory=dict)
    operator_improved: dict = field(default_factory=dict)


def score_tuple(sol: Solution, mode: str = "j_time", j_bound: float | None = None) -> tuple:
    """Lexicographic internal score. mode selects primary minimization."""
    m = sol.metrics
    # hard feasibility assumed by evaluator
    if j_bound is not None and m["J_time"] > j_bound + 1e-9:
        # infeasible for epsilon-constraint: large penalty first
        return (1, m["J_time"] - j_bound, m["makespan"], m["energy"], m["sorties"])
    base = (0,)
    if mode == "j_time":
        return base + (m["J_time"], m["makespan"], m["energy"], m["sorties"])
    if mode == "makespan":
        return base + (m["makespan"], m["J_time"], m["energy"], m["sorties"])
    if mode == "energy":
        return base + (m["energy"], m["J_time"], m["makespan"], m["sorties"])
    if mode == "sorties":
        return base + (m["sorties"], m["J_time"], m["makespan"], m["energy"])
    return base + (m["J_time"], m["makespan"], m["energy"], m["sorties"])


def alns_search(
    start: Solution,
    evaluator: MissionEvaluator,
    decoder: ResourceDecoder,
    seed: int = 2026092301,
    iterations: int = 80,
    t0: float = 0.05,
    cooling: float = 0.99,
    gate_stats: GateStats | None = None,
    mode: str = "j_time",
    j_bound: float | None = None,
) -> tuple[Solution, AlnsLog]:
    rng = random.Random(seed)
    log = AlnsLog(seed=seed, iterations=iterations)
    current = copy.deepcopy(start)
    best = copy.deepcopy(start)
    temp = t0
    names_d = list(DESTROY.keys())
    names_r = list(REPAIR.keys())
    names_l = ["uav_type_change", "mission_split", "service_2opt"]
    for n in names_d + names_r + list(LOCAL.keys()):
        log.operator_scores[n] = 0.0
        log.operator_usage[n] = 0
        log.operator_accepted[n] = 0
        log.operator_improved[n] = 0

    all_boxes = set(evaluator.boxes.box_id)
    t_start = time.time()
    for it in range(iterations):
        dname = rng.choice(names_d)
        rname = rng.choice(names_r)
        log.operator_usage[dname] += 1
        log.operator_usage[rname] += 1
        fn_d = DESTROY[dname]
        if dname in ("worst_timeliness_removal", "related_service_removal"):
            ms, loose = fn_d(current.missions, rng, evaluator)
        else:
            ms, loose = fn_d(current.missions, rng)
        fn_r = REPAIR[rname]
        sol = fn_r(ms, loose, rng, evaluator, decoder, gate_stats)
        if sol is None:
            continue
        if rng.random() < 0.25:
            lname = rng.choice(names_l)
            log.operator_usage[lname] += 1
            ms2 = LOCAL[lname](sol.missions, rng, evaluator, decoder)
            sol2 = evaluate_solution(ms2, evaluator, decoder, gate_stats)
            if sol2 is not None:
                sol = sol2

        cur_s = score_tuple(current, mode, j_bound)
        new_s = score_tuple(sol, mode, j_bound)
        better = new_s < cur_s
        accept = better
        if not accept and new_s[0] == 0:
            delta = (
                (sol.metrics["J_time"] - current.metrics["J_time"])
                + (sol.metrics["makespan"] - current.metrics["makespan"]) / 10000.0
                + (sol.metrics["energy"] - current.metrics["energy"]) / 100.0
                + (sol.metrics["sorties"] - current.metrics["sorties"]) * 0.01
            )
            if delta > 0 and rng.random() < math.exp(-delta / max(temp, 1e-6)):
                accept = True
        if accept:
            current = sol
            log.accepted_moves += 1
            log.operator_accepted[dname] += 1
            log.operator_accepted[rname] += 1
            log.operator_scores[dname] += 1.0 if better else 0.3
            log.operator_scores[rname] += 1.0 if better else 0.3
            if better:
                log.improved_moves += 1
                log.operator_improved[dname] += 1
                log.operator_improved[rname] += 1
            if score_tuple(sol, mode, j_bound) < score_tuple(best, mode, j_bound):
                best = copy.deepcopy(sol)
        temp *= cooling

    log.runtime_s = time.time() - t_start
    covered = set()
    for m in best.missions:
        for bl in m["boxes_by_service"].values():
            covered.update(bl)
    assert covered == all_boxes
    return best, log
