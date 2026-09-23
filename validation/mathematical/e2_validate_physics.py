#!/usr/bin/env python3
"""E2 physics unit tests. Prints E2_PHYSICS_OK on success."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path("/home/ccc/projects/uav-logistics-comms")
sys.path.insert(0, str(ROOT))

from src.common.charging import charge_time_s  # noqa: E402
from src.common.transport_energy import (  # noqa: E402
    equivalent_range_m,
    leg_energy_kwh,
    return_reserve_ok,
)


def main() -> None:
    # equivalent range endpoints
    r0 = equivalent_range_m(0.0, 25000, 20000, 25)
    rf = equivalent_range_m(25.0, 25000, 20000, 25)
    assert abs(r0 - 25000) < 1e-9
    assert abs(rf - 20000) < 1e-9
    # non-increasing in q
    prev = 1e18
    for q in range(0, 26):
        r = equivalent_range_m(float(q), 25000, 20000, 25)
        assert r <= prev + 1e-9
        prev = r

    # energy non-decreasing in q for fixed climb
    prev_e = -1
    for q in [0, 5, 10, 15, 20, 25]:
        e = leg_energy_kwh(10000, 50, 50, q, 70, 25000, 20000, 25, 4.5, 0.72, 0.0)
        assert e >= prev_e - 1e-12
        prev_e = e

    # reserve
    assert return_reserve_ok(3.0, 4.5, 0.2)
    assert not return_reserve_ok(3.7, 4.5, 0.2)

    # charging continuity and endpoints
    t_full = 1800
    assert abs(charge_time_s(0.0, t_full) - t_full) < 1e-9
    assert abs(charge_time_s(1.0, t_full)) < 1e-9
    left = charge_time_s(0.9 - 1e-12, t_full)
    right = charge_time_s(0.9, t_full)
    assert abs(left - right) < 1e-6
    assert abs(left - 0.35 * t_full) < 1e-6

    # time components positive
    from src.common.flight_time import leg_flight_time_s

    t = leg_flight_time_s(50, 1000, 50, 3, 12, 2.5)
    assert t > 0

    print("E2_PHYSICS_OK")


if __name__ == "__main__":
    main()
