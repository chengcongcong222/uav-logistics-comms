# Q2_SEMANTICS

Frozen Q2 interpretation (updated E3.2). Evidence: `SOURCE_GIVEN` / `MODEL_DERIVED` / `MODEL_ASSUMPTION_ACCEPTED`.

## Time origin

`t = 0` is the common emergency mission start.

## Sortie start / takeoff / delivery / hard deadlines

(unchanged from prior freeze)

- `preparation_start_s` = prep/load begin
- takeoff may wait for battery at 100%
- delivery = handover completion at service
- medical: `t_delivery <= expected_deadline`
- first-batch: `t_delivery <= first_deadline`
- both: `hard_deadline = min(...)`
- hard constraints only

## Timeliness — two-level semantics (`E3.2`)

**Level-1 (primary): weighted overdue**

```text
J_late = Σ_b w_b * max(0, t_b − D_b_expected)
```

- `w_b = priority_weight`
- all boxes with expected deadline participate
- unit: priority-weighted seconds
- interpretation: weighted tardiness after the expected delivery time

**Level-2 (secondary): earlier-is-better**

```text
J_norm = Σ_b w_b * (t_b / D_b_expected) / Σ_b w_b
```

- not deleted; demoted from primary objective
- formal name: `weighted_normalized_delivery_time`
- used when `J_late` is equal (including both zero) to prefer earlier overall delivery

These two are **not** collapsed into a single fixed weighted sum.

## Timeliness ordering

```text
TimelinessKey(x) = (J_late(x), J_norm(x))
```

Lexicographic: compare `J_late` first; only if equal (or within numerical tolerance) compare `J_norm`.  
Fewer overdue weighted-seconds dominates “earlier but more overdue”.

## Q2 core objectives (no fixed scalarization)

1. Timeliness `TimelinessKey = (J_late, J_norm)`
2. makespan
3. total_transport_energy
4. sorties

## Dominance (E3.2)

A **timeliness-not-worse** than B iff `TimelinessKey(A) ≤lex TimelinessKey(B)`.

A dominates B iff timeliness-not-worse AND makespan/energy/sorties all ≤ AND at least one strict improvement.

## Multi-stop physics / gates / resources

Unchanged (per-leg payload, T1–T5, UAV+battery calendars, decoder).

## Frozen physics authority

MODEL_FREEZE_V1 / FORMULA_AUDIT / DATA_CONTRACT unchanged in E3.2.
