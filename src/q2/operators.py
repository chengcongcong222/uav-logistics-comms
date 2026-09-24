"""ALNS destroy/repair/local operators for multi-stop packing."""
from __future__ import annotations

import copy
import math
import random
from typing import Callable

from src.q2.evaluator import GateStats, MissionEvaluator
from src.q2.evaluator_sol import evaluate_solution, pack_key


def _boxes_of(ms: list[dict]) -> list[str]:
    out = []
    for m in ms:
        for bl in m["boxes_by_service"].values():
            out.extend(bl)
    return out


def random_box_removal(ms: list[dict], rng: random.Random, k: int = 3) -> tuple[list[dict], list[str]]:
    ms = copy.deepcopy(ms)
    boxes = _boxes_of(ms)
    if not boxes:
        return ms, []
    rm = set(rng.sample(boxes, min(k, len(boxes))))
    return _remove_boxes(ms, rm)


def worst_timeliness_removal(ms: list[dict], rng: random.Random, evaluator: MissionEvaluator, k: int = 3):
    ms = copy.deepcopy(ms)
    # remove boxes from missions with latest hard start (most urgent cluster) — diversify by taking from latest finishes
    scored = []
    for i, m in enumerate(ms):
        urg = 0.0
        for bl in m["boxes_by_service"].values():
            for b in bl:
                urg += float(evaluator.box_idx.loc[b, "priority_weight"])
        scored.append((urg, i))
    scored.sort(reverse=True)
    rm = set()
    for _, i in scored[: max(1, min(2, len(scored)))]:
        bl = _boxes_of([ms[i]])
        rm.update(rng.sample(bl, min(k, len(bl))))
    return _remove_boxes(ms, rm)


def related_service_removal(ms: list[dict], rng: random.Random, evaluator: MissionEvaluator, k: int = 4):
    ms = copy.deepcopy(ms)
    services = []
    for m in ms:
        services.extend(m["service_sequence"])
    if not services:
        return ms, []
    seed = rng.choice(services)
    xy = {r.node_id: (r.x_m, r.y_m) for r in evaluator.nodes.itertuples()}

    def rel(s: str) -> float:
        x0, y0 = xy[seed]
        x1, y1 = xy[s]
        d = math.hypot(x1 - x0, y1 - y0)
        # deadline proximity
        b0 = evaluator.boxes[evaluator.boxes.service_id == seed]
        b1 = evaluator.boxes[evaluator.boxes.service_id == s]
        d0 = float(b0.expected_deadline_s.min()) if len(b0) else 0
        d1 = float(b1.expected_deadline_s.min()) if len(b1) else 0
        return d + 0.01 * abs(d0 - d1)

    ranked = sorted(set(services), key=rel)
    chosen = set(ranked[: min(k, len(ranked))])
    rm = set()
    for m in ms:
        for s in list(m["boxes_by_service"]):
            if s in chosen:
                rm.update(m["boxes_by_service"][s])
    return _remove_boxes(ms, rm)


def whole_mission_removal(ms: list[dict], rng: random.Random, k: int = 1):
    ms = copy.deepcopy(ms)
    if not ms:
        return ms, []
    idxs = list(range(len(ms)))
    rng.shuffle(idxs)
    rm = set()
    for i in idxs[:k]:
        rm.update(_boxes_of([ms[i]]))
    return _remove_boxes(ms, rm)


def route_segment_removal(ms: list[dict], rng: random.Random, k: int = 1):
    """Remove one service stop (its boxes) from a multi-stop mission."""
    ms = copy.deepcopy(ms)
    multi = [m for m in ms if len(m["service_sequence"]) > 1]
    if not multi:
        return whole_mission_removal(ms, rng, 1)
    m = rng.choice(multi)
    s = rng.choice(m["service_sequence"])
    return _remove_boxes(ms, set(m["boxes_by_service"][s]))


def _remove_boxes(ms: list[dict], rm: set[str]) -> tuple[list[dict], list[str]]:
    out = []
    for m in ms:
        by = {}
        for s, bl in m["boxes_by_service"].items():
            keep = [b for b in bl if b not in rm]
            if keep:
                by[s] = keep
        if by:
            m2 = copy.deepcopy(m)
            m2["boxes_by_service"] = by
            m2["service_sequence"] = [s for s in m["service_sequence"] if s in by]
            out.append(m2)
    return out, sorted(rm)


def _insert_box(
    evaluator: MissionEvaluator,
    ms: list[dict],
    box_id: str,
    rng: random.Random,
    mode: str,
) -> list[list[dict]]:
    """Generate candidate solution lists with box inserted."""
    r = evaluator.box_idx.loc[box_id]
    svc = r["service_id"]
    cands: list[list[dict]] = []
    types = list(evaluator.types.index)
    # 1) add to existing stop at same service
    for i, m in enumerate(ms):
        if svc in m["boxes_by_service"]:
            for g in [m["uav_type"]]:
                by = {s: list(bl) for s, bl in m["boxes_by_service"].items()}
                by[svc] = by[svc] + [box_id]
                trial = copy.deepcopy(ms)
                trial[i] = pack_key(g, m["service_sequence"], by)
                cands.append(trial)
    # 2) insert new stop into existing multi mission (limit positions)
    for i, m in enumerate(ms):
        if svc in m["boxes_by_service"]:
            continue
        positions = list(range(len(m["service_sequence"]) + 1))
        if len(positions) > 3:
            positions = positions[:2] + positions[-1:]
        for pos in positions:
            for g in [m["uav_type"]]:
                seq = m["service_sequence"][:pos] + [svc] + m["service_sequence"][pos:]
                by = {s: list(bl) for s, bl in m["boxes_by_service"].items()}
                by[svc] = [box_id]
                trial = copy.deepcopy(ms)
                trial[i] = pack_key(g, seq, by)
                cands.append(trial)
    # 3) new mission
    for g in types:
        trial = copy.deepcopy(ms)
        trial.append(pack_key(g, [svc], {svc: [box_id]}))
        cands.append(trial)
    # Keep every type and insertion position; list order is not a feasibility gate.
    return cands


def best_feasible_insertion(ms, loose, rng, evaluator, decoder, gate_stats=None):
    return _insert_many(ms, loose, evaluator, decoder, gate_stats, strategy="best")


def regret_2_insertion(ms, loose, rng, evaluator, decoder, gate_stats=None):
    return _insert_many(ms, loose, evaluator, decoder, gate_stats, strategy="regret2", rng=rng)


def hard_deadline_first_insertion(ms, loose, rng, evaluator, decoder, gate_stats=None):
    loose_sorted = sorted(
        loose,
        key=lambda b: (
            evaluator.hard_deadline(b) is None,
            evaluator.hard_deadline(b) if evaluator.hard_deadline(b) is not None else 1e18,
            -float(evaluator.box_idx.loc[b, "priority_weight"]),
        ),
    )
    return _insert_many(ms, loose_sorted, evaluator, decoder, gate_stats, strategy="best")


def _repair_key(sol):
    return tuple(sol.metrics[k] for k in ("J_late", "J_norm", "makespan", "energy", "sorties"))


def _insert_many(ms, loose, evaluator, decoder, gate_stats, strategy="best", rng=None):
    ms = copy.deepcopy(ms)
    remaining = list(loose)
    while remaining:
        best_by_box = {}
        for b in remaining:
            options = []
            for cand in _insert_box(evaluator, ms, b, rng, "same"):
                sol = evaluate_solution(cand, evaluator, decoder, gate_stats)
                if sol is not None:
                    options.append(sol)
            if not options:
                best_by_box[b] = None
                continue
            options.sort(key=_repair_key)
            best_by_box[b] = options[0]
            best_by_box[b + "::second"] = options[1] if len(options) > 1 else options[0]
        feasible = [(b, s) for b, s in best_by_box.items() if not b.endswith("::second") and s is not None]
        if not feasible:
            return None
        if strategy == "regret2" and rng is not None:
            def regret(item):
                b, s = item
                s2 = best_by_box[b + "::second"]
                return tuple(b - a for a, b in zip(_repair_key(s), _repair_key(s2))) + tuple(-v for v in _repair_key(s))
            feasible.sort(key=regret, reverse=True)
            b, sol = feasible[0]
        else:
            feasible.sort(key=lambda x: _repair_key(x[1]))
            b, sol = feasible[0]
        ms = sol.missions
        remaining.remove(b)
    sol = evaluate_solution(ms, evaluator, decoder, gate_stats)
    return sol


def service_2opt(ms, rng, evaluator, decoder):
    improved = []
    for m in ms:
        seq = m["service_sequence"]
        if len(seq) < 2:
            improved.append(m)
            continue
        best = m
        for i in range(len(seq)):
            for j in range(i + 1, len(seq)):
                new_seq = seq[:i] + seq[i : j + 1][::-1] + seq[j + 1 :]
                cand = pack_key(m["uav_type"], new_seq, m["boxes_by_service"])
                sol = evaluate_solution([cand], evaluator, decoder)
                if sol is None:
                    continue
                base = evaluate_solution([m], evaluator, decoder)
                if base and sol.metrics["energy"] < base.metrics["energy"] - 1e-9:
                    best = sol.missions[0]
        improved.append(best)
    return improved


def mission_merge(ms, rng, evaluator, decoder):
    from src.q2.initial_solution import _merge_pair

    changed = True
    ms = copy.deepcopy(ms)
    while changed and len(ms) > 1:
        changed = False
        base = evaluate_solution(ms, evaluator, decoder)
        for i in range(len(ms)):
            for j in range(i + 1, len(ms)):
                for cand in _merge_pair(evaluator, ms[i], ms[j]):
                    trial = ms[:i] + ms[i + 1 : j] + ms[j + 1 :] + [cand]
                    sol = evaluate_solution(trial, evaluator, decoder)
                    if sol and sol.metrics["sorties"] == base.metrics["sorties"] - 1:
                        ms = sol.missions
                        changed = True
                        break
                if changed:
                    break
            if changed:
                break
    return ms


def mission_split(ms, rng, evaluator, decoder):
    ms = copy.deepcopy(ms)
    if not ms:
        return ms
    i = rng.randrange(len(ms))
    m = ms[i]
    all_boxes = _boxes_of([m])
    if len(all_boxes) < 2:
        return ms
    b = rng.choice(all_boxes)
    left = {s: [x for x in bl if x != b] for s, bl in m["boxes_by_service"].items()}
    left = {s: bl for s, bl in left.items() if bl}
    svc = evaluator.box_idx.loc[b, "service_id"]
    if not left:
        return ms
    a = pack_key(m["uav_type"], [s for s in m["service_sequence"] if s in left], left)
    c = pack_key(m["uav_type"], [svc], {svc: [b]})
    return ms[:i] + [a, c] + ms[i + 1 :]


def uav_type_change(ms, rng, evaluator, decoder):
    ms = copy.deepcopy(ms)
    types = list(evaluator.types.index)
    for i, m in enumerate(ms):
        others = [g for g in types if g != m["uav_type"]]
        if not others:
            continue
        g = rng.choice(others)
        trial = copy.deepcopy(ms)
        trial[i] = pack_key(g, m["service_sequence"], m["boxes_by_service"])
        sol = evaluate_solution(trial, evaluator, decoder)
        base = evaluate_solution(ms, evaluator, decoder)
        if sol and base and (sol.metrics["sorties"], sol.metrics["energy"]) < (base.metrics["sorties"], base.metrics["energy"]):
            ms = sol.missions
    return ms


DESTROY = {
    "random_box_removal": random_box_removal,
    "worst_timeliness_removal": worst_timeliness_removal,
    "related_service_removal": related_service_removal,
    "whole_mission_removal": whole_mission_removal,
    "route_segment_removal": route_segment_removal,
}
REPAIR = {
    "best_feasible_insertion": best_feasible_insertion,
    "regret_2_insertion": regret_2_insertion,
    "hard_deadline_first_insertion": hard_deadline_first_insertion,
}
LOCAL = {
    "service_2opt": service_2opt,
    "mission_merge": mission_merge,
    "mission_split": mission_split,
    "uav_type_change": uav_type_change,
}
