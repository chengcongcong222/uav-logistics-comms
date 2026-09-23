"""Q2 multi-objective solve: B0/B1, J_time best-known, real epsilon-constraint, true Pareto."""
from __future__ import annotations

import copy
import json
import time

import pandas as pd

from src.common.paths import PROCESSED_DIR, RESULTS_Q2
from src.q2.alns import OBJ_KEYS, alns_search, score_tuple
from src.q2.evaluator import GateStats, MissionEvaluator
from src.q2.evaluator_sol import evaluate_solution
from src.q2.initial_solution import build_b0, build_b1
from src.q2.scheduler import ResourceDecoder

SEEDS = [2026092301 + i for i in range(10)]
EPS_LIST = [0.0, 0.01, 0.02, 0.05]
ITERS_STAGE1 = 80
ITERS_STAGE2 = 40


def load_tables() -> dict:
    return {
        "types": pd.read_csv(PROCESSED_DIR / "transport_uav_types.csv").set_index("uav_type"),
        "nodes": pd.read_csv(PROCESSED_DIR / "nodes.csv"),
        "geom": pd.read_csv(PROCESSED_DIR / "route_geometry.csv"),
        "boxes": pd.read_csv(PROCESSED_DIR / "boxes.csv"),
        "uavs": pd.read_csv(PROCESSED_DIR / "transport_uavs.csv"),
        "batteries": pd.read_csv(PROCESSED_DIR / "transport_batteries.csv"),
    }


def dump_solution(sol, tag: str, evaluator: MissionEvaluator) -> None:
    sorties, deliveries, uav_cal, bat_cal = [], [], [], []
    for m in sol.decoded:
        sorties.append(
            {
                "sortie_id": m.mission_id,
                "uav_id": m.uav_id,
                "uav_type": m.uav_type,
                "battery_id": m.battery_id,
                "preparation_start_s": m.preparation_start_s,
                "takeoff_s": m.takeoff_s,
                "service_sequence": ">".join(m.service_sequence),
                "return_s": m.return_s,
                "energy_kwh": m.energy_kwh,
                "energy_margin_kwh": m.energy_margin_kwh,
                "n_boxes": len(m.box_ids),
                "payload_kg": m.initial_payload_kg,
                "tag": tag,
            }
        )
        uav_cal.append(
            {
                "uav_id": m.uav_id,
                "sortie_id": m.mission_id,
                "busy_start_s": m.preparation_start_s,
                "busy_end_s": m.return_s,
            }
        )
        bat_cal.append(
            {
                "battery_id": m.battery_id,
                "sortie_id": m.mission_id,
                "takeoff_s": m.takeoff_s,
                "return_s": m.return_s,
                "energy_kwh": m.energy_kwh,
            }
        )
        for svc, bl in m.boxes_by_service.items():
            td = m.delivery_times_s[svc]
            for b in bl:
                r = evaluator.box_idx.loc[b]
                hd = evaluator.hard_deadline(b)
                exp = float(r.expected_deadline_s) if pd.notna(r.expected_deadline_s) else None
                deliveries.append(
                    {
                        "box_id": b,
                        "sortie_id": m.mission_id,
                        "service_id": svc,
                        "delivery_time_s": td,
                        "expected_deadline_s": exp,
                        "first_deadline_s": r.first_deadline_s,
                        "hard_deadline_s": hd,
                        "hard_deadline_ok": (hd is None) or (td <= hd + 1e-9),
                        "normalized_delivery_time": (td / exp) if exp else None,
                        "tag": tag,
                    }
                )
    pd.DataFrame(sorties).to_csv(RESULTS_Q2 / f"q2_sorties_{tag}.csv", index=False)
    pd.DataFrame(deliveries).to_csv(RESULTS_Q2 / f"q2_box_delivery_{tag}.csv", index=False)
    pd.DataFrame(uav_cal).to_csv(RESULTS_Q2 / f"q2_uav_calendar_{tag}.csv", index=False)
    pd.DataFrame(bat_cal).to_csv(RESULTS_Q2 / f"q2_battery_calendar_{tag}.csv", index=False)
    pd.DataFrame([{"tag": tag, **sol.metrics}]).to_csv(
        RESULTS_Q2 / f"q2_objectives_{tag}.csv", index=False
    )


def metrics_row(sol, source: str, **extra) -> dict:
    return {
        "source": source,
        **extra,
        **{k: sol.metrics[k] for k in OBJ_KEYS},
        "soft_late_count": sol.metrics.get("soft_late_count"),
    }


def dominates(a: dict, b: dict) -> bool:
    """a dominates b if all objectives <= and at least one <."""
    le = all(float(a[c]) <= float(b[c]) + 1e-12 for c in OBJ_KEYS)
    lt = any(float(a[c]) < float(b[c]) - 1e-12 for c in OBJ_KEYS)
    return le and lt


def nondominated(rows: list[dict]) -> pd.DataFrame:
    """True 4-objective dominance filter (min all)."""
    uniq = []
    seen = set()
    for r in rows:
        key = tuple(round(float(r[c]), 9) for c in OBJ_KEYS)
        if key in seen:
            continue
        seen.add(key)
        uniq.append(r)
    keep = []
    for i, a in enumerate(uniq):
        dominated = False
        for j, b in enumerate(uniq):
            if i == j:
                continue
            # a is dominated if b dominates a
            if dominates(b, a):
                dominated = True
                break
        if not dominated:
            keep.append(a)
    return pd.DataFrame(keep)


def log_operator_stats(log, rows: list, **extra) -> None:
    for op in log.operator_scores:
        usage = log.operator_usage.get(op, 0)
        acc = log.operator_accepted.get(op, 0)
        imp = log.operator_improved.get(op, 0)
        rows.append(
            {
                **extra,
                "operator": op,
                "usage": usage,
                "accepted": acc,
                "improved": imp,
                "success_rate": (imp / usage) if usage else 0.0,
                "score": log.operator_scores.get(op, 0.0),
            }
        )


def main() -> None:
    RESULTS_Q2.mkdir(parents=True, exist_ok=True)
    tables = load_tables()
    evaluator = MissionEvaluator(tables, rho=0.20)
    decoder = ResourceDecoder(tables, rho=0.20)

    print("B0...", flush=True)
    t0 = time.time()
    b0 = build_b0(evaluator, decoder)
    b0_rt = time.time() - t0
    dump_solution(b0, "B0", evaluator)

    print("B1...", flush=True)
    t0 = time.time()
    b1 = build_b1(evaluator, decoder, b0)
    b1_rt = time.time() - t0
    dump_solution(b1, "B1", evaluator)

    # ---- Stage 1: J_time best-known over 10 seeds x 80 iters ----
    print("Stage1 J_time best-known...", flush=True)
    stage1_rows, op_rows = [], []
    best_j = copy.deepcopy(b1)
    for seed in SEEDS:
        sol, log = alns_search(
            b1, evaluator, decoder, seed=seed, iterations=ITERS_STAGE1, mode="j_time"
        )
        stage1_rows.append(
            {
                "seed": seed,
                "iterations": ITERS_STAGE1,
                "runtime_s": log.runtime_s,
                "accepted_moves": log.accepted_moves,
                "improved_moves": log.improved_moves,
                **{k: sol.metrics[k] for k in OBJ_KEYS},
            }
        )
        log_operator_stats(log, op_rows, stage=1, seed=seed)
        if score_tuple(sol, "j_time") < score_tuple(best_j, "j_time"):
            best_j = sol
        print(f"  seed={seed} { {k: sol.metrics[k] for k in OBJ_KEYS} } rt={log.runtime_s:.1f}", flush=True)

    j_best = best_j.metrics["J_time"]
    print("J_time_best_known", j_best, flush=True)
    pd.DataFrame(stage1_rows).to_csv(RESULTS_Q2 / "alns_runs.csv", index=False)

    # stability stats
    s1 = pd.DataFrame(stage1_rows)
    stab = {}
    for c in OBJ_KEYS:
        col = s1[c]
        stab[c] = {
            "best": float(col.min()),
            "median": float(col.median()),
            "mean": float(col.mean()),
            "std": float(col.std()),
            "min": float(col.min()),
            "max": float(col.max()),
            "cv": float(col.std() / col.mean()) if col.mean() else None,
        }
    stab["runtime_s"] = {
        "mean": float(s1.runtime_s.mean()),
        "min": float(s1.runtime_s.min()),
        "max": float(s1.runtime_s.max()),
        "accepted_moves_mean": float(s1.accepted_moves.mean()),
    }
    (RESULTS_Q2 / "stability_summary.json").write_text(json.dumps(stab, indent=2), encoding="utf-8")

    # ---- Stage 2: real epsilon-constraint subproblems ----
    print("Stage2 epsilon-constraint...", flush=True)
    eps_rows = []
    pool = [
        ("B0", b0),
        ("B1", b1),
        ("stage1_best", best_j),
    ]
    for seed, row in zip(SEEDS, stage1_rows):
        # re-search to recover solutions is expensive; keep stage1 best_j as candidate
        pass
    pool.append(("stage1_pool", best_j))

    for eps in EPS_LIST:
        bound = (1.0 + eps) * j_best
        for obj_mode in ("makespan", "energy", "sorties"):
            # start from best_j if feasible else b0
            start = best_j if best_j.metrics["J_time"] <= bound + 1e-9 else b0
            sub_best = None
            for seed in SEEDS[:5]:  # 5 seeds per subproblem to control runtime
                sol, log = alns_search(
                    start,
                    evaluator,
                    decoder,
                    seed=seed,
                    iterations=ITERS_STAGE2,
                    mode=obj_mode,
                    j_bound=bound,
                )
                if sol.metrics["J_time"] <= bound + 1e-9:
                    if sub_best is None or score_tuple(sol, obj_mode) < score_tuple(sub_best, obj_mode):
                        sub_best = sol
                log_operator_stats(log, op_rows, stage=2, seed=seed, eps=eps, obj=obj_mode)
            if sub_best is not None:
                eps_rows.append(
                    metrics_row(
                        sub_best,
                        source="epsilon",
                        eps=eps,
                        obj_mode=obj_mode,
                        j_bound=bound,
                    )
                )
                pool.append((f"eps{eps}_{obj_mode}", sub_best))
                print(f"  eps={eps} obj={obj_mode} { {k: sub_best.metrics[k] for k in OBJ_KEYS} }", flush=True)

    pd.DataFrame(eps_rows).to_csv(RESULTS_Q2 / "q2_epsilon_solutions.csv", index=False)

    # ---- True nondominated set ----
    all_rows = [metrics_row(b0, "B0"), metrics_row(b1, "B1"), metrics_row(best_j, "stage1_best")]
    all_rows.extend(eps_rows)
    # add each stage1 seed as sample
    for seed, sol_seed in zip(SEEDS, [best_j] * len(SEEDS)):
        pass
    for r in stage1_rows:
        all_rows.append(
            {
                "source": "stage1_seed",
                "seed": r["seed"],
                **{k: r[k] for k in OBJ_KEYS},
            }
        )
    pareto = nondominated(all_rows)
    pareto.to_csv(RESULTS_Q2 / "q2_pareto.csv", index=False)
    pd.DataFrame(op_rows).to_csv(RESULTS_Q2 / "operator_stats.csv", index=False)

    # representative = best J_time on pareto, tie makespan/energy/sorties
    pareto_sorted = pareto.sort_values(OBJ_KEYS, kind="mergesort")
    rep = pareto_sorted.iloc[0]
    rep_metrics = {c: float(rep[c]) for c in OBJ_KEYS}
    # recover solution object
    candidates = [b0, b1, best_j] + [s for _, s in pool[3:]]
    rep_sol = best_j
    for s in candidates:
        if all(abs(s.metrics[c] - rep_metrics[c]) < 1e-9 for c in OBJ_KEYS):
            rep_sol = s
            break
    else:
        # pick closest
        rep_sol = min(
            candidates,
            key=lambda s: sum(abs(s.metrics[c] - rep_metrics[c]) for c in OBJ_KEYS),
        )

    dump_solution(rep_sol, "ALNS", evaluator)
    for name in ("sorties", "box_delivery", "uav_calendar", "battery_calendar", "objectives"):
        pd.read_csv(RESULTS_Q2 / f"q2_{name}_ALNS.csv").to_csv(RESULTS_Q2 / f"q2_{name}.csv", index=False)

    # baseline comparison
    rows = [
        {"method": "B0", "runtime_s": b0_rt, **b0.metrics},
        {"method": "B1", "runtime_s": b1_rt, **b1.metrics},
        {"method": "ALNS_representative", "runtime_s": float(s1.runtime_s.mean()), **rep_sol.metrics},
    ]
    pd.DataFrame(rows).to_csv(RESULTS_Q2 / "baseline_comparison.csv", index=False)

    # candidate gate totals with correct ratios
    from src.q2.operators import DESTROY, _insert_box
    import random as _r

    gate_rows = []
    rng = _r.Random(7)
    total = GateStats()
    for opn, fn in DESTROY.items():
        g = GateStats()
        for _ in range(3):
            if opn in ("worst_timeliness_removal", "related_service_removal"):
                m2, loose2 = fn(rep_sol.missions, rng, evaluator, 3)
            else:
                m2, loose2 = fn(rep_sol.missions, rng, 3)
            for b in loose2[:3]:
                for cand in _insert_box(evaluator, m2, b, rng, "same")[:8]:
                    evaluate_solution(cand, evaluator, decoder, g)
        gate_rows.append(g.as_row(opn))
        total.generated += g.generated
        total.accepted += g.accepted
        total.failed_t2 += g.failed_t2
        total.failed_t3 += g.failed_t3
        total.failed_t4 += g.failed_t4
        total.failed_t5 += g.failed_t5
        total.failed_t1 += g.failed_t1
    pd.DataFrame(gate_rows).to_csv(RESULTS_Q2 / "candidate_gate_stats.csv", index=False)
    gen = total.generated
    acc = total.accepted
    tot = {
        "generated": gen,
        "accepted": acc,
        "retention_ratio": (acc / gen) if gen else 0.0,
        "rejection_ratio": (1.0 - acc / gen) if gen else 0.0,
        "failed_mass": total.failed_t2,
        "failed_volume": total.failed_t3,
        "failed_energy": total.failed_t4,
        "failed_relative_deadline": total.failed_t5,
        "failed_service_consistency": total.failed_t1,
    }
    pd.DataFrame([tot]).to_csv(RESULTS_Q2 / "candidate_gate_totals.csv", index=False)

    print("B0", {k: b0.metrics[k] for k in OBJ_KEYS}, flush=True)
    print("B1", {k: b1.metrics[k] for k in OBJ_KEYS}, flush=True)
    print("REP", rep_metrics, flush=True)
    print("retention", tot["retention_ratio"], "rejection", tot["rejection_ratio"], flush=True)
    print("Q2_SOLVED", flush=True)


if __name__ == "__main__":
    main()
