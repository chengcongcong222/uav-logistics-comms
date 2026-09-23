# FORMULA_AUDIT

Source document: problem DOCX (OMML recovered).  
Evidence levels: `SOURCE_GIVEN` / `MODEL_DERIVED` / `MODEL_ASSUMPTION_ACCEPTED`.

## Summary status (after E2.1)

**E2_FORMULA_STATUS = FROZEN_WITH_LABELED_EVIDENCE**  
**None of the three resolved items below may be described as `SOURCE_GIVEN`.**

---

## 1. Equivalent range — `SOURCE_GIVEN`

```text
L_g(q) = L_g^0 − (L_g^0 − L_g^F) · (q / Q_g)^{3/2},   0 ≤ q ≤ Q_g
```

## 2. Horizontal cruise energy (transport) — `MODEL_DERIVED`

```text
E_gij^hor(q) = (d_ij / L_g(q)) · E_g^use
```

Reason: given equivalent range `L_g(q)` and usable energy `E_g^use`, and assuming
constant payload on the leg and linear accumulation of horizontal energy with distance,
energy per meter is `E_g^use / L_g(q)`. This closes the statement information without
claiming a printed equation. **Not `SOURCE_GIVEN`.**

## 3. Climb additional energy — `MODEL_ASSUMPTION_ACCEPTED`

```text
E_up = m · g0 · h+ / (η_up · 3.6e6)     [kWh]
```

- transport: `m = m_g^0 + q`
- relay: `m = m_R^takeoff` (23.5 kg)
- `g0 = 9.80665 m/s²`
- require `0 < η_up ≤ 1` when `h+ > 0`

Reason: field name is **爬升能耗效率** and `η_up = 0.72 < 1`. As a conversion efficiency,
battery energy to gain potential energy `mgh` must be `mgh/η`. The product form `η·mgh`
would consume less than ideal gravitational energy. Relay text says climb uses “the same
relation” with takeoff mass — the transport explicit equation appears omitted from the
statement. Physically consistent form is accepted as an explicit modeling assumption.
**Not `SOURCE_GIVEN`.**

## 4. Descent energy — `SOURCE_GIVEN` (qualitative)

“下降能耗效率取0表示不单独计算下降附加能耗.” All table values are 0 ⇒ **E_down = 0**.
Non-zero descent efficiency is undefined and is **not** extrapolated from climb.

## 5. Return energy reserve — `SOURCE_GIVEN`

```text
E_p^T = Σ E_gij(q_pij) ≤ (1 − ρ_g) · E_g^use
```

## 6. Flight time — `SOURCE_GIVEN`

```text
t_gij = h_ij^+ / v_g^↑ + d_ij / v_g^c + h_ij^- / v_g^↓
```

## 7. Prep / load / handover time — `MODEL_DERIVED`

From field names (“接收点基础交接时间”, “每箱增加交接时间”, “每箱装载时间”):

```text
T_handover = T_base + n · T_per-box
T_load     = n · T_load,box
```

**Not `SOURCE_GIVEN`.**

## 8. Relay energy — mixed

```text
E_R^hor = P_R^cruise · T_R^cruise / 3600          (SOURCE_GIVEN verbal)
E_R^up  = m_R^takeoff · g0 · h+ / (η_R^up · 3.6e6) (MODEL_ASSUMPTION_ACCEPTED, same as §3)
E_R^service = (P_R^hover + P_R^comm) · T_R^service / 3600   (SOURCE_GIVEN verbal)
```

## 9. Two-stage charging — `SOURCE_GIVEN`

```text
t_chg(s) = T_full · [0.65·(0.90 − s)/0.90 + 0.35],   0 ≤ s < 0.90
         = T_full · 0.35·(1 − s)/0.10,               0.90 ≤ s ≤ 1
```

## 10. Cruise altitude rule — `SOURCE_GIVEN`

```text
planned_cruise_altitude = max DEM elevation along leg + 50 m
O01 operation altitude = ground elevation
service operation altitude = ground elevation + 30 m
```

---

## Evidence table (frozen)

| item | evidence |
| --- | --- |
| `L_g(q)` | SOURCE_GIVEN |
| `E_hor = (d/L(q))E_use` | MODEL_DERIVED |
| `E_up = mgh/(η·3.6e6)` | MODEL_ASSUMPTION_ACCEPTED |
| `E_down = 0` | SOURCE_GIVEN |
| return reserve | SOURCE_GIVEN |
| flight time | SOURCE_GIVEN |
| handover / load stacking | MODEL_DERIVED |
| two-stage charge | SOURCE_GIVEN |
