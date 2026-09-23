"""Simplified robust parse of communication parameters."""
from __future__ import annotations

import json
import math
from dataclasses import dataclass

import pandas as pd

from src.common.paths import PROCESSED_DIR, RESULTS_DIR

RESULTS_Q3 = RESULTS_DIR / "q3"


@dataclass
class RadioEndpoint:
    name: str
    pt_dbm: float
    gt_dbi: float
    gr_dbi: float


@dataclass
class PropParams:
    f_mhz: float
    l_sys_db: float
    l_obs_db: float
    p_sens_dbm: float
    margin_db: float


def load_comm_params() -> tuple[PropParams, dict[str, RadioEndpoint]]:
    raw = json.loads((PROCESSED_DIR / "communication_parameters.json").read_text(encoding="utf-8"))

    def find(container: dict, *needles: str) -> float:
        for _cat, items in container.items():
            if not isinstance(items, dict):
                continue
            for name, ent in items.items():
                if any(n in str(name) for n in needles) and isinstance(ent, dict) and "value" in ent:
                    return float(ent["value"])
        raise KeyError(needles)

    params = PropParams(
        f_mhz=find(raw, "载波", "MHz"),
        l_sys_db=find(raw, "系统损耗"),
        l_obs_db=find(raw, "遮挡"),
        p_sens_dbm=find(raw, "灵敏度"),
        margin_db=find(raw, "衰落"),
    )

    def ep(cat: str) -> tuple[float, float]:
        items = raw["endpoints"][cat]
        pt = float(next(v["value"] for n, v in items.items() if "发射功率" in n))
        gt = float(next(v["value"] for n, v in items.items() if "天线增益" in n))
        return pt, gt

    pt_t, g_t = ep("运输无人机")
    pt_ra, g_ra = ep("中继接入端")
    pt_rb, g_rb = ep("中继回传端")
    pt_g, g_g = ep("固定网关 G01")
    endpoints = {
        "transport": RadioEndpoint("transport", pt_t, g_t, g_t),
        "relay_access": RadioEndpoint("relay_access", pt_ra, g_ra, g_ra),
        "relay_backhaul": RadioEndpoint("relay_backhaul", pt_rb, g_rb, g_rb),
        "g01": RadioEndpoint("g01", pt_g, g_g, g_g),
    }
    return params, endpoints


def lmax_one_way(params: PropParams, tx: RadioEndpoint, rx: RadioEndpoint) -> float:
    return tx.pt_dbm + tx.gt_dbi + rx.gr_dbi - params.l_sys_db - params.p_sens_dbm - params.margin_db


def lmax_bidirectional(params: PropParams, a: RadioEndpoint, b: RadioEndpoint) -> float:
    return min(lmax_one_way(params, a, b), lmax_one_way(params, b, a))


def fspl_db(f_mhz: float, d_m: float) -> float:
    d_km = max(d_m, 1e-6) / 1000.0
    return 32.45 + 20.0 * math.log10(f_mhz) + 20.0 * math.log10(d_km)


def path_loss_db(params: PropParams, d_m: float, blocked: bool) -> float:
    return fspl_db(params.f_mhz, d_m) + (params.l_obs_db if blocked else 0.0)


def margin_db(l_max: float, l_path: float) -> float:
    return l_max - l_path


def distance_m(a, b) -> float:
    return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2)


def pair_lmax() -> dict[str, float]:
    params, eps = load_comm_params()
    return {
        "transport<->G01": lmax_bidirectional(params, eps["transport"], eps["g01"]),
        "transport<->relay": lmax_bidirectional(params, eps["transport"], eps["relay_access"]),
        "relay<->G01": lmax_bidirectional(params, eps["relay_backhaul"], eps["g01"]),
    }


def build_link_budget_table() -> pd.DataFrame:
    params, _ = load_comm_params()
    rows = []
    for pair, lm in pair_lmax().items():
        rows.append(
            {
                "pair": pair,
                "L_max_db": lm,
                "f_mhz": params.f_mhz,
                "L_obs_db": params.l_obs_db,
                "L_sys_db": params.l_sys_db,
                "P_sens_dbm": params.p_sens_dbm,
                "M_db": params.margin_db,
            }
        )
    return pd.DataFrame(rows)


def max_range_m(l_max: float, params: PropParams, blocked: bool) -> float:
    budget = l_max - (params.l_obs_db if blocked else 0.0)
    x = budget - 32.45 - 20.0 * math.log10(params.f_mhz)
    return (10 ** (x / 20.0)) * 1000.0


if __name__ == "__main__":
    RESULTS_Q3.mkdir(parents=True, exist_ok=True)
    df = build_link_budget_table()
    df.to_csv(RESULTS_Q3 / "link_budget.csv", index=False)
    params, _ = load_comm_params()
    for _, r in df.iterrows():
        d0 = max_range_m(r.L_max_db, params, False)
        d1 = max_range_m(r.L_max_db, params, True)
        print(f"{r.pair}\tLmax={r.L_max_db:.3f}\tD_los_m={d0:.1f}\tD_obs_m={d1:.1f}")
    print(df.to_string(index=False))
    print("LINK_BUDGET_OK")
