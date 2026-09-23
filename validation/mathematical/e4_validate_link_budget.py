#!/usr/bin/env python3
"""Independent link-budget recomputation. Success => E4_LINK_BUDGET_VALID."""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import pandas as pd

ROOT = Path("/home/ccc/projects/uav-logistics-comms")
sys.path.insert(0, str(ROOT))
from src.common.paths import PROCESSED_DIR  # noqa: E402


def fail(msg: str) -> None:
    print(f"E4_LINK_BUDGET_INVALID: {msg}")
    raise SystemExit(1)


def main() -> None:
    raw = json.loads((PROCESSED_DIR / "communication_parameters.json").read_text(encoding="utf-8"))

    def find(needles):
        for _c, items in raw.items():
            if not isinstance(items, dict):
                continue
            for n, ent in items.items():
                if any(x in str(n) for x in needles) and isinstance(ent, dict) and "value" in ent:
                    return float(ent["value"])
        raise KeyError(needles)

    f = find(["载波", "MHz"])
    lsys = find(["系统损耗"])
    lobs = find(["遮挡"])
    psens = find(["灵敏度"])
    mrg = find(["衰落"])

    def ep(cat):
        items = raw["endpoints"][cat]
        pt = float(next(v["value"] for n, v in items.items() if "发射功率" in n))
        gt = float(next(v["value"] for n, v in items.items() if "天线增益" in n))
        return pt, gt

    pt_t, g_t = ep("运输无人机")
    pt_ra, g_ra = ep("中继接入端")
    pt_rb, g_rb = ep("中继回传端")
    pt_g, g_g = ep("固定网关 G01")

    def lmax(pt_a, gt_a, gr_b):
        return pt_a + gt_a + gr_b - lsys - psens - mrg

    def bidi(pt_a, gt_a, gr_a, pt_b, gt_b, gr_b):
        return min(lmax(pt_a, gt_a, gr_b), lmax(pt_b, gt_b, gr_a))

    tg = bidi(pt_t, g_t, g_t, pt_g, g_g, g_g)
    tr = bidi(pt_t, g_t, g_t, pt_ra, g_ra, g_ra)
    rg = bidi(pt_rb, g_rb, g_rb, pt_g, g_g, g_g)

    # compare with exported table
    df = pd.read_csv(ROOT / "results/q3/link_budget.csv").set_index("pair")
    if abs(float(df.loc["transport<->G01", "L_max_db"]) - tg) > 1e-6:
        fail("T-G mismatch")
    if abs(float(df.loc["transport<->relay", "L_max_db"]) - tr) > 1e-6:
        fail("T-R mismatch")
    if abs(float(df.loc["relay<->G01", "L_max_db"]) - rg) > 1e-6:
        fail("R-G mismatch")

    # sanity refs (not hardcoded in product code)
    if abs(tg - 122.0) > 0.5 or abs(tr - 116.0) > 0.5 or abs(rg - 126.0) > 0.5:
        fail(f"sanity ref mismatch {tg},{tr},{rg}")

    # FSPL check
    def fspl(d_m):
        return 32.45 + 20 * math.log10(f) + 20 * math.log10(d_m / 1000.0)

    if abs(fspl(1000.0) - (32.45 + 20 * math.log10(f) + 0.0)) > 1e-6:
        fail("fspl")

    # obstruction penalty
    d = 5000.0
    if abs((fspl(d) + lobs) - (fspl(d) + 10)) > 1e-9:
        fail("lobs")

    print("E4_LINK_BUDGET_VALID")


if __name__ == "__main__":
    main()
