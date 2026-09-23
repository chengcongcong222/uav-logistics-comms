# FORMULA_AUDIT

Source document: problem DOCX (OMML recovered). Tags: `SOURCE_GIVEN` / `SOURCE_DERIVED` / `ASSUMPTION_REQUIRED`.

## Summary status

**E2_FORMULA_STATUS = PARTIAL_WITH_GAPS**  
**MODEL_FREEZE implication: BLOCKED until climb-energy explicit form is confirmed.**

Horizontal cruise energy for **relay** is SOURCE_GIVEN (power × time).  
Horizontal cruise energy for **transport** is not printed as an explicit algebraic formula; it is **SOURCE_DERIVED** from the given equivalent-range definition (derivation below).  
Climb additional energy for transport/relay is **not printed**; only “爬升能耗效率” is in the data table → **ASSUMPTION_REQUIRED**.

---

## 1. Equivalent range — `SOURCE_GIVEN`

```text
L_g(q) = L_g^0 − (L_g^0 − L_g^F) · (q / Q_g)^{3/2},   0 ≤ q ≤ Q_g
```

- `g` type, `q` payload (kg), `L_g^0` empty range, `L_g^F` full range (m), `Q_g` max payload (kg)

## 2. Horizontal cruise energy (transport) — `SOURCE_DERIVED` (gap vs strict explicit form)

Statement gives only:

```text
E_gij(q) = E_gij^hor(q) + E_gij^up(q)
```

and defines equivalent range `L_g(q)`. There is **no printed** `E_gij^hor(·)` formula.

**Derivation used (must be confirmed at MODEL_FREEZE):**  
If `L_g(q)` is the range obtainable from usable energy at payload `q`, then energy per meter is `E_g^use / L_g(q)`, hence

```text
E_gij^hor(q) = (d_ij / L_g(q)) · E_g^use
```

This is a consequence of the definition, not a free guess — but it is **not** an explicit SOURCE_GIVEN equation.

## 3. Climb additional energy — `ASSUMPTION_REQUIRED` (gap)

Statement names `E_gij^up(q)` and provides `爬升能耗效率` / `下降能耗效率` in the workbook (descent eff = 0 ⇒ no descent term). **No formula** relating efficiency, mass, climb height to kWh appears in DOCX.

**Working assumption (labeled, not frozen):**

```text
E_gij^up(q) = η_up · m_total · g0 · h_ij^+ / 3.6e6     [kWh]
```

with `g0 = 9.80665 m/s²`, `m_total = empty_mass + q` (transport) or `takeoff_mass` (relay).

## 4. Descent energy — `SOURCE_GIVEN` (qualitative)

“下降能耗效率取0表示不单独计算下降附加能耗.” Data has descent efficiency 0 ⇒ **E_down = 0**.

## 5. Return energy reserve — `SOURCE_GIVEN`

```text
E_p^T = Σ_{(i,j)∈p} E_gij(q_pij) ≤ (1 − ρ_g) · E_g^use
```

## 6. Flight time — `SOURCE_GIVEN`

```text
t_gij = h_ij^+ / v_g^↑ + d_ij / v_g^c + h_ij^- / v_g^↓
```

## 7. Prep / load / handover time — `SOURCE_GIVEN` (parameters only)

From `运输无人机数据.xlsx`: fixed prep, per-box load, handover base + per-box.  
Service time on station = handover_base + n_boxes × handover_per_box (structure implied by parameter names; **ASSUMPTION_REQUIRED** on the exact stacking if not spelled as an equation).

## 8. Relay flight energy — `SOURCE_GIVEN` (horizontal) + same climb gap

Verbatim: “水平巡航能耗根据巡航功率和巡航时间计算，爬升附加能耗按上述相同关系计算，质量取计划起飞总质量”.  
⇒ `E_hor^R = P_cruise · t_cruise` (`SOURCE_GIVEN`).  
⇒ `E_up^R` uses the same climb relation as transport (`ASSUMPTION_REQUIRED` as in §3).  
Service energy: hover power + comm extra power over service duration (`SOURCE_GIVEN` verbal).

## 9. Two-stage charging — `SOURCE_GIVEN`

```text
t_chg(s) = T_full · [0.65·(0.90 − s)/0.90 + 0.35],   0 ≤ s < 0.90
         = T_full · 0.35·(1 − s)/0.10,               0.90 ≤ s ≤ 1
```

Boundary continuous at `s=0.9` (`0.35·T_full`). `t_chg(0)=T_full`, `t_chg(1)=0`.

## 10. Cruise altitude rule — `SOURCE_GIVEN`

```text
planned_cruise_altitude = max DEM elevation along leg + 50 m
O01 operation altitude = ground elevation
service operation altitude = ground elevation + 30 m
```

---

## Gap list for MODEL_FREEZE

1. **Climb additional energy explicit formula** — not in DOCX (`ASSUMPTION_REQUIRED`).
2. **Transport horizontal energy** — only derivable from equivalent range, not printed (`SOURCE_DERIVED`).
3. Handover time stacking is parameter-level (`ASSUMPTION_REQUIRED` on exact sum form).

Until (1) is confirmed, treat overall formula gate as **E2_FORMULA_BLOCKED** for freeze purposes, even if Q1 baseline runs under labeled assumptions.
