"""ALNS with simulated-annealing acceptance (searcher only)."""
from __future__ import annotations

import copy
import math
import random
import time
from dataclasses import dataclass, field

from src.q2.evaluator import GateStats, MissionEvaluator
from src.q2.evaluator_sol import Solution, evaluate_solution, internal_score
from src.q2.operators import DESTROY, LOCAL, REPAIR
from src.q2.scheduler import ResourceDecoder


@dataclass
class AlnsLog:
    seed: int = 0
    iterations: int = 0
    accepted_moves: int = 0
    runtime_s: float = 0.0
    best_trajectory: list[float] = field(default_factory=list)
    operator_scores: dict = field(default_factory=dict)
    operator_usage: dict = field(default_factory=dict)


def alns_search(
    start: Solution,
    evaluator: MissionEvaluator,
    decoder: ResourceDecoder,
    seed: int = 2026092301,
    iterations: int = 80,
    t0: float = 0.05,
    cooling: float = 0.985,
    gate_stats: GateStats | None = None,
) -> tuple[Solution, AlnsLog]:
    rng = random.Random(seed)
    log = AlnsLog(seed=seed, iterations=iterations)
    current = copy.deepcopy(start)
    best = copy.deepcopy(start)
    temp = t0
    names_d = list(DESTROY.keys())
    names_r = list(REPAIR.keys())
    names_l = list(LOCAL.keys())
    for n in names_d + names_r + names_l:
        log.operator_scores[n] = 0.0
        log.operator_usage[n] = 0

    all_boxes = set(evaluator.boxes.box_id)
    t_start = time.time()
    for it in range(iterations):
        dname = rng.choice(names_d)
        rname = rng.choice(names_r)
        log.operator_usage[dname] += 1
        log.operator_usage[rname] += 1
        fn_d = DESTROY[dname]
        # destroy
        if dname in ("worst_timeliness_removal", "related_service_removal"):
            ms, loose = fn_d(current.missions, rng, evaluator)
        else:
            ms, loose = fn_d(current.missions, rng)
        # repair
        fn_r = REPAIR[rname]
        sol = fn_r(ms, loose, rng, evaluator, decoder, gate_stats)
        if sol is None:
            continue
        # occasional local improve (cheap ops only most of the time)
        if rng.random() < 0.2:
            lname = rng.choice(["uav_type_change", "mission_split", "service_2opt"])
            log.operator_usage[lname] += 1
            ms2 = LOCAL[lname](sol.missions, rng, evaluator, decoder)
            sol2 = evaluate_solution(ms2, evaluator, decoder, gate_stats)
            if sol2 is not None:
                sol = sol2
                log.operator_scores[lname] += 0.5

        cur_s = internal_score(current)
        new_s = internal_score(sol)
        better = new_s < cur_s
        accept = better
        if not accept:
            # SA on J_time/makespan/energy normalized
            delta = (
                (sol.metrics["J_time"] - current.metrics["J_time"])
                + (sol.metrics["makespan"] - current.metrics["makespan"]) / 10000.0
                + (sol.metrics["energy"] - current.metrics["energy"]) / 100.0
            )
            if delta > 0 and rng.random() < math.exp(-delta / max(temp, 1e-6)):
                accept = True
        if accept:
            current = sol
            log.accepted_moves += 1
            log.operator_scores[dname] += 1.0 if better else 0.3
            log.operator_scores[rname] += 1.0 if better else 0.3
            if internal_score(sol) < internal_score(best):
                best = copy.deepcopy(sol)
                log.best_trajectory.append(best.metrics["energy"])
        temp *= cooling
        if it % 10 == 0:
            log.best_trajectory.append(best.metrics["J_time"])

    log.runtime_s = time.time() - t_start
    # coverage check
    covered = set()
    for m in best.missions:
        for bl in m["boxes_by_service"].values():
            covered.update(bl)
    assert covered == all_boxes
    return best, log
