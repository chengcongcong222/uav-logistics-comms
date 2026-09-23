# Q2_SEMANTICS

Frozen Q2 interpretation. Evidence: `SOURCE_GIVEN` / `MODEL_DERIVED` / `MODEL_ASSUMPTION_ACCEPTED`.

## Time origin

`t = 0` is the common emergency mission start (`SOURCE_GIVEN` task setup / `MODEL_DERIVED` convention).

## Sortie start `s_p`

`preparation_start_s`: moment preparation/loading **begins** (not takeoff). (`MODEL_DERIVED`)

## Takeoff

```text
t_takeoff = max( s_p + T_prep + n_p * T_load_per_box ,  t_battery_ready )
```

Battery must be 100% at takeoff (`SOURCE_GIVEN`: recharge to 100% before reuse).  
Prep/load **may overlap** previous recharge of the assigned battery; only takeoff requires full charge (`MODEL_DERIVED`).

## Delivery completion

Delivery time of boxes at a stop = **when handover at that service finishes**, not arrival:

```text
t_delivery(S_i) = arrival_i + T_handover_base + n_i * T_handover_per_box
```

(`SOURCE_GIVEN` field names + `MODEL_DERIVED` stacking).

After drop, UAV departs from service operation altitude (ground+30 m) toward the next leg.

## Hard deadlines

- medical: `t_delivery <= expected_deadline` (`SOURCE_GIVEN`)
- first-batch: `t_delivery <= first_deadline` (`SOURCE_GIVEN`)
- if both: `hard_deadline = min(expected, first)` (`MODEL_DERIVED`)
- hard constraints only; no soft-penalty acceptance of violations

## Timeliness objective (continuous)

```text
J_time = Σ_b w_b * (t_b / D_b_expected) / Σ_b w_b
```

over boxes with expected deadline. Early delivery scores `<1`.  
Also report `soft_late_count`, `soft_lateness_sum`, `max_soft_lateness`.

## Objectives (raw)

```text
J1 = J_time
J2 = makespan = max return_O01 over transport UAVs
J3 = total_transport_energy
J4 = number_of_sorties
```

Hard feasibility always ranks above objectives. No fixed weighted sum as the sole objective.

## Multi-stop physics

Per-leg payload after each drop; **no** distance×average-payload shortcut. Geometry from `data/processed/route_geometry.csv`.

## Five physical gates (candidate shrink)

| gate | check |
| --- | --- |
| T1 | box uniqueness / same-service consistency of a stop |
| T2 | mass ≤ type max payload |
| T3 | volume ≤ type cargo volume |
| T4 | energy + return reserve `E ≤ (1-ρ)E_use` |
| T5 | relative deadline reachability if started at t=0 |

## Resource calendars (MODEL_DERIVED)

- UAV busy: `preparation_start` → `return_O01`
- Battery cycle: `takeoff` → `return` → recharge to 100% (`t_ready_next`)
- Battery ID and UAV ID chosen by deterministic decoder, not by ALNS genes

## Frozen physics authority

`docs/model/MODEL_FREEZE_V1.md`, `docs/model/FORMULA_AUDIT.md`, `docs/model/DATA_CONTRACT.md` — do not modify formulas in E3.
