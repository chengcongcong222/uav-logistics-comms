"""Q2 end-to-end solve: B0, B1, ALNS, epsilon Pareto, exports (streamlined)."""
from __future__ import annotations

import copy
import json
import time

import pandas as pd

from src.common.paths import PROCESSED_DIR, RESULTS_Q2
from src.q2.alns import alns_search
from src.q2.evaluator import GateStats, MissionEvaluator
from src.q2.evaluator_sol import evaluate_solution, internal_score
from src.q2.initial_solution import build_b0, build_b1
from src.q2.scheduler import ResourceDecoder


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
        uav_cal.append({"uav_id": m.uav_id, "sortie_id": m.mission_id, "busy_start_s": m.preparation_start_s, "busy_end_s": m.return_s})
        bat_cal.append({"battery_id": m.battery_id, "sortie_id": m.mission_id, "takeoff_s": m.takeoff_s, "return_s": m.return_s, "energy_kwh": m.energy_kwh})
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
    pd.DataFrame([{"tag": tag, **sol.metrics}]).to_csv(RESULTS_Q2 / f"q2_objectives_{tag}.csv", index=False)


def main() -> None:
    RESULTS_Q2.mkdir(parents=True, exist_ok=True)
    tables = load_tables()
    evaluator = MissionEvaluator(tables, rho=0.20)
    decoder = ResourceDecoder(tables, rho=0.20)

    print("building B0...", flush=True)
    t0 = time.time()
    b0 = build_b0(evaluator, decoder)
    b0_rt = time.time() - t0
    dump_solution(b0, "B0", evaluator)
    print("B0", b0.metrics, "rt", b0_rt, flush=True)

    print("building B1...", flush=True)
    t0 = time.time()
    b1 = build_b1(evaluator, decoder, b0)
    b1_rt = time.time() - t0
    dump_solution(b1, "B1", evaluator)
    print("B1", b1.metrics, "rt", b1_rt, flush=True)

    seeds = [2026092301 + i for i in range(10)]
    eps_list = [0.0, 0.01, 0.02, 0.05]
    print("ALNS multi-seed...", flush=True)
    # one J1* run + 10 seeds (single ALNS batch), then classify into epsilon bands
    best_j1, _ = alns_search(b1, evaluator, decoder, seed=seeds[0], iterations=20)
    j1_star = best_j1.metrics["J_time"]
    print("j1_star", j1_star, flush=True)

    pareto_rows, alns_rows, op_rows = [], [], []
    best_all = best_j1
    for seed in seeds:
        t1 = time.time()
        sol, log = alns_search(b1, evaluator, decoder, seed=seed, iterations=12)
        rt = time.time() - t1
        for eps in eps_list:
            bound = (1 + eps) * j1_star
            alns_rows.append(
                {
                    "eps": eps,
                    "seed": seed,
                    "J_time": sol.metrics["J_time"],
                    "makespan": sol.metrics["makespan"],
                    "energy": sol.metrics["energy"],
                    "sorties": sol.metrics["sorties"],
                    "runtime_s": rt,
                    "accepted_moves": log.accepted_moves,
                    "j1_bound": bound,
                }
            )
            if sol.metrics["J_time"] <= bound + 1e-9:
                pareto_rows.append({"eps": eps, "seed": seed, **{k: sol.metrics[k] for k in ("J_time", "makespan", "energy", "sorties")}})
        for op, sc in log.operator_scores.items():
            op_rows.append({"eps": -1, "seed": seed, "operator": op, "score": sc, "usage": log.operator_usage.get(op, 0)})
        if internal_score(sol) < internal_score(best_all):
            best_all = sol
        print(f"seed={seed} {sol.metrics} rt={rt:.1f}", flush=True)

    # gate stats: sample destroy+insert
    from src.q2.operators import DESTROY, _insert_box
    import random as _r

    gate_rows = []
    rng = _r.Random(7)
    for opn, fn in DESTROY.items():
        g = GateStats()
        for _ in range(3):
            if opn in ("worst_timeliness_removal", "related_service_removal"):
                m2, loose2 = fn(best_all.missions, rng, evaluator, 3)
            else:
                m2, loose2 = fn(best_all.missions, rng, 3)
            for b in loose2[:3]:
                for cand in _insert_box(evaluator, m2, b, rng, "same")[:8]:
                    evaluate_solution(cand, evaluator, decoder, g)
        gate_rows.append(g.as_row(opn))
    pd.DataFrame(gate_rows).to_csv(RESULTS_Q2 / "candidate_gate_stats.csv", index=False)

    pd.DataFrame(alns_rows).to_csv(RESULTS_Q2 / "alns_runs.csv", index=False)
    pd.DataFrame(op_rows).to_csv(RESULTS_Q2 / "operator_stats.csv", index=False)
    pd.DataFrame(pareto_rows).drop_duplicates().to_csv(RESULTS_Q2 / "q2_pareto.csv", index=False)

    dump_solution(best_all, "ALNS", evaluator)
    for name in ("sorties", "box_delivery", "uav_calendar", "battery_calendar", "objectives"):
        pd.read_csv(RESULTS_Q2 / f"q2_{name}_ALNS.csv").to_csv(RESULTS_Q2 / f"q2_{name}.csv", index=False)

    df = pd.DataFrame(alns_rows)
    stab = df.groupby("seed")[["J_time", "makespan", "energy", "sorties"]].first().reset_index()
    summary = {
        "best": stab[["J_time", "makespan", "energy", "sorties"]].min().to_dict(),
        "median": stab[["J_time", "makespan", "energy", "sorties"]].median().to_dict(),
        "std": stab[["J_time", "makespan", "energy", "sorties"]].std().to_dict(),
        "runtime_mean_s": float(df.runtime_s.mean()),
    }
    (RESULTS_Q2 / "stability_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    rows = []
    for tag, sol, rt in (("B0", b0, b0_rt), ("B1", b1, b1_rt), ("ALNS", best_all, float(df.runtime_s.mean()))):
        rows.append({"method": tag, "runtime_s": rt, **sol.metrics})
    pd.DataFrame(rows).to_csv(RESULTS_Q2 / "baseline_comparison.csv", index=False)

    # contraction ratio
    gs_tot = {}
    for r in gate_rows:
        for k, v in r.items():
            if k != "operator":
                gs_tot[k] = gs_tot.get(k, 0) + int(v)
    gen = gs_tot.get("generated", 0)
    acc = gs_tot.get("accepted_candidate", 0)
    gs_tot["contraction_ratio"] = (acc / gen) if gen else 0.0
    pd.DataFrame([gs_tot]).to_csv(RESULTS_Q2 / "candidate_gate_totals.csv", index=False)

    print("B0", b0.metrics, flush=True)
    print("B1", b1.metrics, flush=True)
    print("ALNS", best_all.metrics, flush=True)
    print("Q2_SOLVED", flush=True)


if __name__ == "__main__":
    main()
