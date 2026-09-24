"""E3.2: reaudit existing Q2 solutions under J_late/J_norm and build new Pareto."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pandas as pd

from src.q2.alns import OBJ_KEYS, alns_search, score_tuple
from src.q2.evaluator import MissionEvaluator
from src.q2.evaluator_sol import evaluate_solution, pack_key, timeliness_key
from src.q2.scheduler import ResourceDecoder
from src.q2.solve_q2 import dump_solution, load_tables
from src.q2.export_trace import build_trace

ROOT = Path("/home/ccc/projects/uav-logistics-comms")
RESULTS_Q2 = ROOT / "results/q2"
EPS_DIR = RESULTS_Q2 / "epsilon_schedules"
PAR_DIR = RESULTS_Q2 / "pareto_schedules"


def load_raw_from(path: Path) -> list:
    sorties = pd.read_csv(path / "q2_sorties.csv")
    delivery = pd.read_csv(path / "q2_box_delivery.csv")
    raw = []
    for s in sorties.itertuples():
        by = (
            delivery[delivery.sortie_id == s.sortie_id]
            .groupby("service_id")
            .box_id.apply(list)
            .to_dict()
        )
        raw.append(pack_key(s.uav_type, str(s.service_sequence).split(">"), by))
    return raw


def save_full(sol, ev, pdir: Path, meta: dict) -> None:
    pdir.mkdir(parents=True, exist_ok=True)
    tag = meta.get("tag", pdir.name)
    dump_solution(sol, tag, ev)
    for name in ("sorties", "box_delivery", "uav_calendar", "battery_calendar"):
        shutil.copy(RESULTS_Q2 / f"q2_{name}_{tag}.csv", pdir / f"q2_{name}.csv")
    (pdir / "missions.json").write_text(
        json.dumps(sol.missions, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (pdir / "metadata.json").write_text(
        json.dumps(
            {
                **meta,
                "J_late": sol.metrics["J_late"],
                "J_norm": sol.metrics["J_norm"],
                "makespan": sol.metrics["makespan"],
                "energy": sol.metrics["energy"],
                "sorties": sol.metrics["sorties"],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    # write official names then trace
    for name in ("sorties", "box_delivery", "uav_calendar", "battery_calendar"):
        shutil.copy(pdir / f"q2_{name}.csv", RESULTS_Q2 / f"q2_{name}.csv")
    try:
        build_trace().to_csv(pdir / "transport_trace.csv", index=False)
    except Exception as e:  # noqa: BLE001
        print("trace fail", pdir, e, flush=True)


def dominates_e32(a: dict, b: dict) -> bool:
    ta = (a["J_late"], a["J_norm"])
    tb = (b["J_late"], b["J_norm"])
    tim_le = (ta[0] < tb[0] - 1e-12) or (
        abs(ta[0] - tb[0]) <= 1e-9 and ta[1] <= tb[1] + 1e-12
    )
    le = all(float(a[c]) <= float(b[c]) + 1e-12 for c in ("makespan", "energy", "sorties"))
    lt = (
        abs(ta[0] - tb[0]) > 1e-12
        or abs(ta[1] - tb[1]) > 1e-12
        or any(float(a[c]) < float(b[c]) - 1e-12 for c in ("makespan", "energy", "sorties"))
    )
    # strict in at least one of the four aspects
    strict = (ta[0] < tb[0] - 1e-12) or (
        abs(ta[0] - tb[0]) <= 1e-9 and ta[1] < tb[1] - 1e-12
    ) or any(float(a[c]) < float(b[c]) - 1e-12 for c in ("makespan", "energy", "sorties"))
    return tim_le and le and strict


def nondominated_e32(rows: list[dict]) -> pd.DataFrame:
    keep = []
    for i, a in enumerate(rows):
        if any(dominates_e32(b, a) for j, b in enumerate(rows) if i != j):
            continue
        keep.append(a)
    return pd.DataFrame(keep)


def row_of(sol, source: str, **extra) -> dict:
    return {
        "source": source,
        **extra,
        "J_late": sol.metrics["J_late"],
        "J_norm": sol.metrics["J_norm"],
        "makespan": sol.metrics["makespan"],
        "energy": sol.metrics["energy"],
        "sorties": sol.metrics["sorties"],
    }


def main() -> None:
    tables = load_tables()
    ev = MissionEvaluator(tables, 0.2)
    dec = ResourceDecoder(tables, 0.2)

    # ---- Part 7: reaudit existing ----
    print("reaudit existing...", flush=True)
    cands: list[tuple[str, object]] = []
    for name in ("B0", "B1"):
        p = RESULTS_Q2 / f"q2_sorties_{name}.csv"
        if p.exists():
            # use tag folder if present else tag csv
            folder = RESULTS_Q2 / f"q2_sorties_{name}.csv"
            raw = load_raw_from(RESULTS_Q2) if False else None
            # load from tag csv pair
            sorties = pd.read_csv(RESULTS_Q2 / f"q2_sorties_{name}.csv")
            delivery = pd.read_csv(RESULTS_Q2 / f"q2_box_delivery_{name}.csv")
            raw = []
            for s in sorties.itertuples():
                by = (
                    delivery[delivery.sortie_id == s.sortie_id]
                    .groupby("service_id")
                    .box_id.apply(list)
                    .to_dict()
                )
                raw.append(pack_key(s.uav_type, str(s.service_sequence).split(">"), by))
            sol = evaluate_solution(raw, ev, dec)
            if sol:
                cands.append((name, sol))

    for pdir in sorted(PAR_DIR.glob("P*")):
        if (pdir / "q2_sorties.csv").exists():
            sol = evaluate_solution(load_raw_from(pdir), ev, dec)
            if sol:
                cands.append((pdir.name, sol))

    for pdir in sorted(RESULTS_Q2.glob("q2_sorties_*.csv")):
        tag = pdir.stem.replace("q2_sorties_", "")
        if tag in ("B0", "B1") or tag.startswith("P"):
            continue
        try:
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
                raw.append(pack_key(s.uav_type, str(s.service_sequence).split(">"), by))
            sol = evaluate_solution(raw, ev, dec)
            if sol:
                cands.append((tag, sol))
        except Exception:  # noqa: BLE001
            pass

    rows = [row_of(s, name) for name, s in cands]
    pd.DataFrame(rows).to_csv(RESULTS_Q2 / "e32_existing_solution_reaudit.csv", index=False)
    old_pareto = pd.read_csv(RESULTS_Q2 / "q2_pareto.csv") if (RESULTS_Q2 / "q2_pareto.csv").exists() else pd.DataFrame()
    new_pareto_rows = nondominated_e32(rows)
    print("existing", len(rows), "new_pareto", len(new_pareto_rows), flush=True)
    print(new_pareto_rows[["source", "J_late", "J_norm", "makespan", "energy", "sorties"]].to_string(index=False), flush=True)

    # always re-run Stage1+Stage2 under new semantics to get formal records
    b0 = dict(cands).get("B0") or cands[0][1]
    b1 = dict(cands).get("B1") or cands[0][1]
    seeds = [2026092301 + i for i in range(10)]
    print("Stage1 timeliness...", flush=True)
    stage_rows = []
    best_tl = b1
    for seed in seeds:
        sol, log = alns_search(b1, ev, dec, seed=seed, iterations=80, mode="timeliness")
        stage_rows.append(
            {
                "seed": seed,
                "iterations": 80,
                "runtime_s": log.runtime_s,
                "accepted_moves": log.accepted_moves,
                **{k: sol.metrics[k] for k in ("J_late", "J_norm", "makespan", "energy", "sorties")},
            }
        )
        if score_tuple(sol, "timeliness") < score_tuple(best_tl, "timeliness"):
            best_tl = sol
        print(f"  seed={seed} late={sol.metrics['J_late']:.3f} norm={sol.metrics['J_norm']:.5f} makespan={sol.metrics['makespan']:.1f} E={sol.metrics['energy']:.3f} N={sol.metrics['sorties']}", flush=True)
    pd.DataFrame(stage_rows).to_csv(RESULTS_Q2 / "alns_runs_e32.csv", index=False)

    j_late_best = best_tl.metrics["J_late"]
    zero_late = j_late_best <= 1e-9
    if zero_late:
        # J_norm best among zero-late
        zrows = [r for r in stage_rows if r["J_late"] <= 1e-9]
        if not zrows:
            zrows = stage_rows
        j_norm_best = min(r["J_norm"] for r in zrows)
        bound_kind = "J_norm"
        budget_base = j_norm_best
    else:
        bound_kind = "J_late"
        budget_base = j_late_best
    print("J_late_best", j_late_best, "zero_late", zero_late, "bound_kind", bound_kind, "budget_base", budget_base, flush=True)

    # Stage2 epsilon
    print("Stage2 epsilon...", flush=True)
    EPS_DIR.mkdir(parents=True, exist_ok=True)
    eps_sols = []
    for eps in [0.0, 0.01, 0.02, 0.05]:
        bound = (1.0 + eps) * budget_base
        for obj_mode in ("makespan", "energy", "sorties"):
            start = best_tl
            try:
                sol, log = alns_search(
                    start,
                    ev,
                    dec,
                    seed=2026092501,
                    iterations=30,
                    mode=obj_mode,
                    j_bound=bound,
                    bound_kind=bound_kind,
                )
            except RuntimeError as e:
                print(f"  eps={eps} {obj_mode}: {e}", flush=True)
                continue
            meta = {
                "tag": f"EPS{eps}_{obj_mode}",
                "seed": 2026092501,
                "iterations": 30,
                "epsilon": eps,
                "timeliness_budget_type": bound_kind,
                "timeliness_bound": bound,
                "objective_mode": obj_mode,
            }
            save_full(sol, ev, EPS_DIR / meta["tag"], meta)
            eps_sols.append(sol)
            print(f"  eps={eps} {obj_mode} late={sol.metrics['J_late']:.3f} norm={sol.metrics['J_norm']:.5f} makespan={sol.metrics['makespan']:.1f} E={sol.metrics['energy']:.3f} N={sol.metrics['sorties']}", flush=True)

    # true E3.2 Pareto
    all_rows = [row_of(b0, "B0"), row_of(b1, "B1"), row_of(best_tl, "stage1_best")]
    for r in stage_rows:
        all_rows.append({"source": "stage1_seed", "seed": r["seed"], "J_late": r["J_late"], "J_norm": r["J_norm"], "makespan": r["makespan"], "energy": r["energy"], "sorties": r["sorties"]})
    for s in eps_sols:
        all_rows.append(row_of(s, "epsilon"))
    par = nondominated_e32(all_rows)
    par.to_csv(RESULTS_Q2 / "q2_pareto_e32.csv", index=False)

    # rebuild P01..PK from real solutions matching pareto rows
    sols = [("B0", b0), ("B1", b1), ("stage1_best", best_tl)] + [(f"eps{i}", s) for i, s in enumerate(eps_sols)]
    # also attach stage1 seed solutions? we only kept best_tl object — use metrics match on stage rows not objects
    # persist each nondominated point that has a sol object
    PAR_DIR.mkdir(parents=True, exist_ok=True)
    # clear old P*
    for p in PAR_DIR.glob("P*"):
        shutil.rmtree(p, ignore_errors=True)
    k = 0
    for _, prow in par.iterrows():
        match = None
        for name, s in sols:
            if (
                abs(s.metrics["J_late"] - prow["J_late"]) < 1e-6
                and abs(s.metrics["J_norm"] - prow["J_norm"]) < 1e-8
                and abs(s.metrics["makespan"] - prow["makespan"]) < 1e-3
                and abs(s.metrics["energy"] - prow["energy"]) < 1e-6
                and int(s.metrics["sorties"]) == int(prow["sorties"])
            ):
                match = s
                break
        if match is None:
            continue
        k += 1
        pid = f"P{k:02d}"
        save_full(match, ev, PAR_DIR / pid, {"tag": pid, "source": prow.get("source"), "pareto_id": pid})
        print("P", pid, match.metrics["J_late"], match.metrics["J_norm"], match.metrics["makespan"], match.metrics["energy"], match.metrics["sorties"], flush=True)

    (RESULTS_Q2 / "e32_summary.json").write_text(
        json.dumps(
            {
                "J_late_best_known": j_late_best,
                "J_norm_best_known": None if not zero_late else budget_base,
                "bound_kind": bound_kind,
                "zero_late": zero_late,
                "n_pareto": int(k),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print("E32_SOLVED", flush=True)


if __name__ == "__main__":
    main()
