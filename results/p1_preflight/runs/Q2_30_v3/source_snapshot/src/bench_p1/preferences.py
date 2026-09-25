"""P1 preference generation and finite-vector checks; NOT a UAV solver/auditor."""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import random
from pathlib import Path
from typing import Sequence

OBJECTIVES = {
    "Q2": ["J_norm", "makespan_s", "energy_kwh", "transport_sorties"],
    "Q3": ["J_norm", "joint_makespan_s", "total_energy_kwh", "transport_sorties", "relay_sorties"],
}


def compositions(total: int, parts: int):
    if total < 0 or parts < 1:
        raise ValueError("Require total >= 0 and parts >= 1")
    if parts == 1:
        yield (total,)
    else:
        for first in range(total + 1):
            for tail in compositions(total - first, parts - 1):
                yield (first,) + tail


def search_weights(d: int, h: int = 4, inward: float = 0.1) -> list[list[float]]:
    if d < 2 or h < 1 or not 0 < inward < 1:
        raise ValueError("Invalid preference-grid parameters")
    rows = [[(1-inward)*n/h + inward/d for n in a] for a in compositions(h, d)]
    rows += [[float(i == j) for i in range(d)] for j in range(d)]
    rows += [[1/d] * d]
    seen, result = set(), []
    for row in rows:
        key = tuple(round(x, 14) for x in row)
        if key not in seen:
            seen.add(key)
            result.append(row)
    return result


def evaluation_weights(d: int, count: int, seed: int) -> list[list[float]]:
    if d < 2 or count < 1:
        raise ValueError("Invalid evaluation-set dimensions")
    rng = random.Random(seed)
    result = []
    for _ in range(count):
        vals = [-math.log1p(-rng.random()) for _ in range(d)]
        # Protect the measure-zero all-zero draw without inserting a biased row.
        while min(vals) <= 0:
            vals = [-math.log1p(-rng.random()) for _ in range(d)]
        denom = sum(vals)
        result.append([v/denom for v in vals])
    return result


def vector(values: Sequence[float]) -> tuple[float, ...]:
    out = tuple(float(x) for x in values)
    if not out or not all(math.isfinite(x) for x in out):
        raise ValueError("Require a nonempty finite vector")
    return out


def exact_dominates(a: Sequence[float], b: Sequence[float]) -> bool:
    """Mathematical finite-vector check. Not the repository's tolerance auditor."""
    a, b = vector(a), vector(b)
    if len(a) != len(b):
        raise ValueError("Dimension mismatch")
    return all(x <= y for x, y in zip(a, b)) and any(x < y for x, y in zip(a, b))


def nondominated_indices(rows: Sequence[Sequence[float]]) -> list[int]:
    points = [vector(r) for r in rows]
    if points and any(len(p) != len(points[0]) for p in points):
        raise ValueError("Dimension mismatch")
    seen, keep = set(), []
    for i, point in enumerate(points):
        if point in seen:
            continue
        seen.add(point)
        if not any(exact_dominates(other, point) for other in points):
            keep.append(i)
    return keep


def normalize(values: Sequence[float], offsets: Sequence[float], scales: Sequence[float]) -> tuple[float, ...]:
    v, a, s = vector(values), vector(offsets), vector(scales)
    if not len(v) == len(a) == len(s) or min(s) <= 0:
        raise ValueError("Require matching dimensions and strictly positive scales")
    # Do not clip: clipping could conceal a better/worse out-of-range result.
    return tuple((x-y)/z for x, y, z in zip(v, a, s))


def weighted_score(values: Sequence[float], weights: Sequence[float]) -> float:
    v, w = vector(values), vector(weights)
    if len(v) != len(w) or min(w) < 0 or not math.isclose(sum(w), 1, abs_tol=1e-12):
        raise ValueError("Require matching, nonnegative unit-sum weights")
    return math.fsum(x*y for x, y in zip(v, w))


def budget_indices(rows: Sequence[Sequence[float]], caps: dict[int, float]) -> list[int]:
    points = [vector(r) for r in rows]
    if points and any(len(p) != len(points[0]) for p in points):
        raise ValueError("Dimension mismatch")
    for k, cap in caps.items():
        if not isinstance(k, int) or k < 0 or not math.isfinite(float(cap)):
            raise ValueError("Invalid budget")
        if points and k >= len(points[0]):
            raise ValueError("Budget dimension out of range")
    return [i for i, p in enumerate(points) if all(p[k] <= cap for k, cap in caps.items())]


def build_manifest() -> dict:
    result = {"schema": "P1_PREFERENCES_V1", "not_real_disaster_weights": True,
              "scope": "finite preference coverage; no claim of all continuous weights", "sets": {}}
    for scope, names in OBJECTIVES.items():
        d = len(names)
        result["sets"][scope] = {"objectives": names, "search_weights": search_weights(d),
            "evaluation_only_weights": evaluation_weights(d, 64, 26092500+d),
            "evaluation_seed": 26092500+d,
            "recipe": "H=4 simplex lattice, inward=0.1, plus axes and equal weights; evaluation: normalized iid exponential draws"}
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    data = json.dumps(build_manifest(), ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(data, encoding="utf-8")
    print(json.dumps({"path": str(args.out), "sha256": hashlib.sha256(data.encode()).hexdigest(),
        "counts": {k: {"search": len(v["search_weights"]), "evaluation_only": len(v["evaluation_only_weights"])}
                   for k, v in build_manifest()["sets"].items()}}, ensure_ascii=False))

if __name__ == "__main__":
    main()
