# MODEL_FREEZE_V1

## Decision

**MODEL_FREEZE_BLOCKED**

Reason (unique remaining formula issue): the problem DOCX does **not** print an explicit algebraic formula for climb additional energy `E_up` (only the symbol and `爬升能耗效率`). Horizontal cruise energy for transport is also not printed as an equation; it is **SOURCE_DERIVED** from the given equivalent-range formula.

Do not treat this file as a scientific freeze until the formula audit gap is closed or the working assumptions are explicitly accepted.

## Frozen-in-place items (data/geometry; OK)

| item | status |
| --- | --- |
| Coordinate system | lon/lat EPSG:4326 kept; plane EPSG:32649 |
| DEM index rule | row0=north, lon/lat nearest cell, CRS 4326 |
| Cruise altitude rule | max DEM along leg + 50 m |
| Operation altitude | O01=ground; service=ground+30 m |
| Payload definition | box mass sum on outbound; 0 after drop |
| Equivalent range | `L(q)=L0-(L0-Lf)(q/Q)^{3/2}` **SOURCE_GIVEN** |
| Flight time | `h+/v↑ + d/vc + h-/v↓` **SOURCE_GIVEN** |
| Return reserve | `E ≤ (1-ρ)E_use` **SOURCE_GIVEN** |
| SOC / charging | two-stage `t_chg(s)` **SOURCE_GIVEN** |
| Q1 objective priority | (1) min flights (2) min energy (3) min total time |
| Shared structures | see `docs/model/DATA_CONTRACT.md` |

## NOT frozen (blocking)

1. **Climb energy `E_up` explicit formula** — `ASSUMPTION_REQUIRED` currently `η_up·m·g0·h+/3.6e6`.
2. **Transport `E_hor` as printed equation** — currently `SOURCE_DERIVED`: `(d/L(q))·E_use`.
3. Handover time stacking exact form — parameter-level (`base + n·per`).

## Next human gate

Review `docs/model/FORMULA_AUDIT.md` + `results/q1/Q1_REPORT.md`. If assumptions (1)–(2) are accepted or corrected, re-issue `MODEL_FREEZE_V1`.
