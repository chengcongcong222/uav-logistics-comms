# MODEL_FREEZE_V1

## Decision

**MODEL_FROZEN**

Issued after E2.1 physics correction. Evidence levels are explicit and must not be overstated.

## Evidence levels

| level | meaning |
| --- | --- |
| `SOURCE_GIVEN` | printed in problem DOCX / attachment tables |
| `MODEL_DERIVED` | closed form derived from given definitions (not printed as an equation) |
| `MODEL_ASSUMPTION_ACCEPTED` | physically consistent modeling choice accepted for freeze |

## Frozen energy / geometry model

### Equivalent range — `SOURCE_GIVEN`

```text
L_g(q) = L_g^0 − (L_g^0 − L_g^F) · (q / Q_g)^{3/2}
```

### Horizontal cruise energy (transport) — `MODEL_DERIVED`

```text
E_gij^hor(q) = E_g^use · d_ij / L_g(q)
```

### Climb additional energy — `MODEL_ASSUMPTION_ACCEPTED`

```text
E_up = (m · g0 · h+) / (η_up · 3.6e6)     [kWh]
```

- transport `m = m_g^0 + q`
- relay `m = m_R^takeoff`
- require `0 < η_up ≤ 1` if `h+ > 0`

### Descent energy — `SOURCE_GIVEN`

```text
E_down = 0
```

(All attachment descent efficiencies are 0. Non-zero value is undefined and raises.)

### Total leg energy

```text
E_gij = E_gij^hor + E_gij^up
```

### Relay energy — mixed evidence

```text
E_R^hor = P_cruise · T_cruise / 3600                 SOURCE_GIVEN (verbal)
E_R^up  = m_takeoff · g0 · h+ / (η_up · 3.6e6)       MODEL_ASSUMPTION_ACCEPTED
E_R^service = (P_hover + P_comm) · T_service / 3600  SOURCE_GIVEN (verbal)
```

### Other frozen items

| item | evidence |
| --- | --- |
| Coordinates lon/lat + UTM 49N | SOURCE_GIVEN / MODEL_DERIVED |
| DEM index: row0=north, lon/lat cell | SOURCE_GIVEN / MODEL_DERIVED |
| Cruise alt = max DEM along leg + 50 m | SOURCE_GIVEN |
| O01 op alt = ground; service = ground+30 m | SOURCE_GIVEN |
| Payload: outbound q, return 0 | MODEL_DERIVED |
| Flight time 3-phase | SOURCE_GIVEN |
| Return reserve `E ≤ (1-ρ)E_use` | SOURCE_GIVEN |
| Two-stage charging `t_chg(s)` | SOURCE_GIVEN |
| Handover `base+n·per`; load `n·per` | MODEL_DERIVED |
| Q1 priority: min flights → min energy → min time | MODEL_DERIVED (from Q1 wording) |

## Q1 baseline after freeze (ρ=20%)

- flights: 18
- total energy: **59.1066 kWh**
- total time: 32715.6 s

See `results/q1/Q1_REPORT.md` and `results/e2/climb_formula_correction.md`.

## Shared data structures

`docs/model/DATA_CONTRACT.md`

## Exclusions (still binding)

RL / Lyapunov / artificial potential field / new MAC / relay-relay multihop / AODV-OLSR as schedule replacement — all prohibited.

## Next gate

`E3_Q2_TRANSPORT_SCHEDULING`
