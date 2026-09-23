"""E3.1 Stage2 + finalize: real epsilon-constraint (light), true Pareto, exports."""
from __future__ import annotations

import random

import pandas as pd

from src.common.paths import RESULTS_Q2
from src.q2.alns import OBJ_KEYS, alns_search, score_tuple
from src.q2.evaluator import GateStats, MissionEvaluator
from src.q2.evaluator_sol import evaluate_solution
from src.q2.initial_solution import pack_key
from src.q2.operators import DESTROY, _insert_box
from src.q2.scheduler import ResourceDecoder
from src.q2.solve_q2 import dump_solution, load_tables, metrics_row, nondominated


def load_solution_from_csv(tag: str):
    sorties = pd.read_csv(RESULTS_Q2 / f"q2_sorties_{tag}.csv")
    delivery = pd.read_csv(RESULTS_Q2 / f"q2_box_delivery_{tag}.csv")
    raw = []
    for s in sorties.itertuples():
        by = (
            delivery[delivery.sortie_id == s.sortie_id]
            .groupby("service_id")
            .box_id.apply(list)
            .to_dict()
        )
        seq = str(s.service_sequence).split(">")
        raw.append(pack_key(s.uav_type, seq, by))
    return raw


def main() -> None:
    tables = load_tables()
    evaluator = MissionEvaluator(tables, rho=0.20)
    decoder = ResourceDecoder(tables, rho=0.20)

    print("reload B0/B1...", flush=True)
    b0 = evaluate_solution(load_solution_from_csv("B0"), evaluator, decoder)
    b1 = evaluate_solution(load_solution_from_csv("B1"), evaluator, decoder)
    assert b0 and b1

    s1 = pd.read_csv(RESULTS_Q2 / "alns_runs.csv")
    j_best = float(s1.J_time.min())
    print("J_time_best_known", j_best, flush=True)

    print("Stage2 epsilon...", flush=True)
    eps_rows = []
    op_rows = []
    extra_sols = []
    incumbent = None
    for eps in [0.0, 0.01, 0.02, 0.05]:
        bound = (1.0 + eps) * j_best
        for obj_mode in ("makespan", "energy", "sorties"):
            if incumbent is not None and incumbent.metrics["J_time"] <= bound + 1e-9:
                start = incumbent
            elif b1.metrics["J_time"] <= bound + 1e-9:
                start = b1
            else:
                start = b0
            sub_best = None
            for seed in (2026092401, 2026092402):
                sol, log = alns_search(
                    start,
                    evaluator,
                    decoder,
                    seed=seed,
                    iterations=25,
                    mode=obj_mode,
                    j_bound=bound,
                )
                if sol.metrics["J_time"] <= bound + 1e-9:
                    if sub_best is None or score_tuple(sol, obj_mode) < score_tuple(
                        sub_best, obj_mode
                    ):
                        sub_best = sol
                for op in log.operator_scores:
                    usage = log.operator_usage.get(op, 0)
                    acc = log.operator_accepted.get(op, 0)
                    imp = log.operator_improved.get(op, 0)
                    op_rows.append(
                        {
                            "stage": 2,
                            "seed": seed,
                            "eps": eps,
                            "obj": obj_mode,
                            "operator": op,
                            "usage": usage,
                            "accepted": acc,
                            "improved": imp,
                            "success_rate": (imp / usage) if usage else 0.0,
                            "score": log.operator_scores.get(op, 0.0),
                        }
                    )
            if sub_best is not None:
                if incumbent is None or score_tuple(sub_best, "j_time") < score_tuple(incumbent, "j_time"):
                    incumbent = sub_best
                eps_rows.append(
                    metrics_row(
                        sub_best, source="epsilon", eps=eps, obj_mode=obj_mode, j_bound=bound
                    )
                )
                extra_sols.append(sub_best)
                print(
                    f"  eps={eps} obj={obj_mode} { {k: sub_best.metrics[k] for k in OBJ_KEYS} }",
                    flush=True,
                )

    pd.DataFrame(eps_rows).to_csv(RESULTS_Q2 / "q2_epsilon_solutions.csv", index=False)

    all_rows = [metrics_row(b0, "B0"), metrics_row(b1, "B1")]
    for r in s1.to_dict("records"):
        all_rows.append(
            {"source": "stage1_seed", "seed": r["seed"], **{k: r[k] for k in OBJ_KEYS}}
        )
    all_rows.extend(eps_rows)
    pareto = nondominated(all_rows)
    pareto.to_csv(RESULTS_Q2 / "q2_pareto.csv", index=False)
    print("pareto rows", len(pareto), flush=True)

    cands = [b0, b1] + extra_sols
    rep_sol = min(
        cands,
        key=lambda s: (
            s.metrics["J_time"],
            s.metrics["makespan"],
            s.metrics["energy"],
            s.metrics["sorties"],
        ),
    )
    dump_solution(rep_sol, "ALNS", evaluator)
    for name in ("sorties", "box_delivery", "uav_calendar", "battery_calendar", "objectives"):
        pd.read_csv(RESULTS_Q2 / f"q2_{name}_ALNS.csv").to_csv(
            RESULTS_Q2 / f"q2_{name}.csv", index=False
        )

    pd.DataFrame(op_rows).to_csv(RESULTS_Q2 / "operator_stats.csv", index=False)

    gate_rows = []
    total = GateStats()
    rng = random.Random(7)
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
    gen, acc = total.generated, total.accepted
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

    pd.DataFrame(
        [
            {"method": "B0", **{k: b0.metrics[k] for k in OBJ_KEYS}},
            {"method": "B1", **{k: b1.metrics[k] for k in OBJ_KEYS}},
            {"method": "ALNS_representative", **{k: rep_sol.metrics[k] for k in OBJ_KEYS}},
        ]
    ).to_csv(RESULTS_Q2 / "baseline_comparison.csv", index=False)

    print("REP", {k: rep_sol.metrics[k] for k in OBJ_KEYS}, flush=True)
    print("retention", tot["retention_ratio"], "rejection", tot["rejection_ratio"], flush=True)
    print("Q2_SOLVED", flush=True)


if __name__ == "__main__":
    main()
