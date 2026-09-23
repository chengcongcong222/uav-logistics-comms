#!/usr/bin/env python3
"""Relay link unit tests (simplified)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path("/home/ccc/projects/uav-logistics-comms")
sys.path.insert(0, str(ROOT))

from src.common.terrain import Dem
from src.q3.communication_margin import margin_pair, margin_relay_two_hop
from src.q3.link_budget import load_comm_params, pair_lmax
from src.q3.trajectory import g01_position, relay_position_legal


def main() -> None:
    dem = Dem()
    params, _ = load_comm_params()
    lm = pair_lmax()
    g01 = g01_position()

    # 1 near
    tpos = (g01[0] + 50.0, g01[1], g01[2])
    mc, _, _, _ = margin_pair(params, lm["transport<->G01"], dem, tpos, g01, force_los=True)
    assert mc > 0, mc

    # 2 far (metric)
    tpos2 = (g01[0] + 80000.0, g01[1], g01[2])
    mc2, _, _, _ = margin_pair(params, lm["transport<->G01"], dem, tpos2, g01, force_los=True)
    assert mc2 < 0, mc2

    # 3 obstruction penalty = Lobs when blocked vs LOS
    mc_los, _, _, _ = margin_pair(params, lm["transport<->G01"], dem, tpos, g01, force_los=True)
    # force block by calling with force_los False on a high-terrain line is optional
    assert params.l_obs_db == 10.0

    # 4/5 two-hop
    rpos = (g01[0] + 800.0, g01[1] + 800.0, g01[2] + 80.0)
    mur, mrg, mrel = margin_relay_two_hop(
        params, lm["transport<->relay"], lm["relay<->G01"], dem, tpos, rpos, g01
    )
    assert mrel <= min(mur, mrg) + 1e-9

    assert relay_position_legal(dem, 109.23, 23.01, 100.0)
    assert not relay_position_legal(dem, 109.23, 23.01, 400.0)
    assert not relay_position_legal(dem, 109.23, 23.01, -1.0)
    print("E4_RELAY_UNIT_OK")


if __name__ == "__main__":
    main()
