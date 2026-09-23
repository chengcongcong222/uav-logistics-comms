"""B0 single-service baseline and B1 greedy multi-stop merge."""
from __future__ import annotations

import copy

import pandas as pd

from src.q2.evaluator import MissionEvaluator
from src.q2.evaluator_sol import Solution, evaluate_solution, pack_key
from src.q2.scheduler import ResourceDecoder


def _try_pack(
    evaluator: MissionEvaluator,
    service: str,
    batch: list[str],
    type_load: dict[str, int] | None = None,
) -> tuple[str, dict] | None:
    """Pick a feasible type; balance type_load when provided (prefer free capacity)."""
    type_load = type_load or {}
    best = None
    for g in evaluator.types.index:
        m = evaluator.evaluate_mission(g, {service: batch}, [service])
        if m is None:
            continue
        # lower load first, then earlier finish, then lower energy
        cand = (type_load.get(g, 0), m.relative_return_time, m.energy_kwh, g)
        if best is None or cand < best[0]:
            best = (cand, g, m)
    if best is None:
        return None
    return best[1], pack_key(best[1], [service], {service: list(batch)})


def _pack_service(evaluator: MissionEvaluator, service: str, items: list[str]) -> list[dict]:
    """Hard-deadline boxes in small early flights; soft boxes in larger flights."""
    hard, soft = [], []
    for b in items:
        hd = evaluator.hard_deadline(b)
        (hard if hd is not None else soft).append(b)
    hard.sort(key=lambda b: (evaluator.hard_deadline(b), -float(evaluator.box_idx.loc[b, "mass_kg"])))
    soft.sort(key=lambda b: -float(evaluator.box_idx.loc[b, "mass_kg"]))

    raw: list[dict] = []
    type_load = getattr(_pack_service, "_type_load", None)
    if type_load is None:
        type_load = {}
        _pack_service._type_load = type_load

    def greedy(batch_list: list[str], max_n: int) -> None:
        remaining = list(batch_list)
        while remaining:
            placed = False
            for n in range(min(max_n, len(remaining)), 0, -1):
                batch = remaining[:n]
                got = _try_pack(evaluator, service, batch, type_load)
                if got:
                    g, spec = got
                    type_load[g] = type_load.get(g, 0) + 1
                    raw.append(spec)
                    remaining = [b for b in remaining if b not in set(batch)]
                    placed = True
                    break
            if not placed:
                raise RuntimeError(f"pack fail {service} {remaining}")

    greedy(hard, 3)
    greedy(soft, 6)
    return raw


def build_b0(evaluator: MissionEvaluator, decoder: ResourceDecoder) -> Solution:
    _pack_service._type_load = {}
    raw: list[dict] = []
    for service in sorted(evaluator.boxes.service_id.unique()):
        items = list(evaluator.boxes[evaluator.boxes.service_id == service].box_id)
        raw.extend(_pack_service(evaluator, service, items))
    print("B0 type_load", dict(_pack_service._type_load), "sorties", len(raw))
    sol = evaluate_solution(raw, evaluator, decoder)
    if sol is None:
        # extreme parallelism fallback: 1-2 boxes per sortie
        raw = []
        for service in sorted(evaluator.boxes.service_id.unique()):
            items = list(evaluator.boxes[evaluator.boxes.service_id == service].box_id)
            items.sort(key=lambda b: (evaluator.hard_deadline(b) is None, evaluator.hard_deadline(b) or 0))
            i = 0
            while i < len(items):
                placed = False
                for n in (2, 1):
                    batch = items[i : i + n]
                    got = _try_pack(evaluator, service, batch)
                    if got:
                        raw.append(got[1])
                        i += n
                        placed = True
                        break
                if not placed:
                    raise RuntimeError(f"fallback fail {service}")
        sol = evaluate_solution(raw, evaluator, decoder)
    if sol is None:
        raise RuntimeError("B0 schedule decode failed")
    return sol


def _merge_pair(evaluator: MissionEvaluator, a: dict, b: dict) -> list[dict]:
    out = []
    sa = a["service_sequence"][0] if len(a["service_sequence"]) == 1 else None
    sb = b["service_sequence"][0] if len(b["service_sequence"]) == 1 else None
    if sa is not None and sb is not None and sa == sb:
        boxes = a["boxes_by_service"][sa] + b["boxes_by_service"][sb]
        for g in evaluator.types.index:
            out.append(pack_key(g, [sa], {sa: boxes}))
        return out
    if sa is None or sb is None:
        return out
    for g in evaluator.types.index:
        for seq in ([sa, sb], [sb, sa]):
            by = {sa: list(a["boxes_by_service"][sa]), sb: list(b["boxes_by_service"][sb])}
            out.append(pack_key(g, seq, by))
    return out


def build_b1(evaluator: MissionEvaluator, decoder: ResourceDecoder, b0: Solution) -> Solution:
    current = [copy.deepcopy(m) for m in b0.missions]
    improved = True
    rounds = 0
    while improved and rounds < 3:
        rounds += 1
        improved = False
        base = evaluate_solution(current, evaluator, decoder)
        if base is None:
            break
        best_delta = None
        best_sol_missions = None
        n = len(current)
        # only try merges among nearest service pairs (limit cost)
        xy = {r.node_id: (r.x_m, r.y_m) for r in evaluator.nodes.itertuples()}
        for i in range(n):
            for j in range(i + 1, n):
                sa = current[i]["service_sequence"][0] if len(current[i]["service_sequence"]) == 1 else None
                sb = current[j]["service_sequence"][0] if len(current[j]["service_sequence"]) == 1 else None
                if sa is None or sb is None:
                    continue
                x0, y0 = xy[sa]
                x1, y1 = xy[sb]
                if (x1 - x0) ** 2 + (y1 - y0) ** 2 > 15000 ** 2:
                    continue
                for cand in _merge_pair(evaluator, current[i], current[j])[:4]:
                    trial = current[:i] + current[i + 1 : j] + current[j + 1 :] + [cand]
                    sol = evaluate_solution(trial, evaluator, decoder)
                    if sol is None:
                        continue
                    cur = (
                        base.metrics["sorties"],
                        base.metrics["energy"],
                        base.metrics["makespan"],
                        base.metrics["J_time"],
                    )
                    new = (
                        sol.metrics["sorties"],
                        sol.metrics["energy"],
                        sol.metrics["makespan"],
                        sol.metrics["J_time"],
                    )
                    if new < cur:
                        delta = (cur[0] - new[0], cur[1] - new[1], cur[2] - new[2], cur[3] - new[3])
                        if best_delta is None or delta > best_delta:
                            best_delta = delta
                            best_sol_missions = sol.missions
        if best_sol_missions is not None:
            current = best_sol_missions
            improved = True
    sol = evaluate_solution(current, evaluator, decoder)
    if sol is None:
        raise RuntimeError("B1 decode failed")
    return sol
