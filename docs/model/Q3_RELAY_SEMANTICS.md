# Q3_RELAY_SEMANTICS (E5)

## Relay mission pattern

O01 → climb → cruise → descend → **hover site R** → link setup (30 s) → service → climb → cruise → descend → O01.

Cruise altitude:

```text
H_cruise = max(max_DEM_on_O01-R_route + 50 m, z_R)
```

Hover: `0 < h_AGL = z_R − DEM(x_R,y_R) ≤ 300 m`.

## Energy (E5)

```text
E_hor = P_cruise * T_horizontal / 3600     SOURCE_GIVEN
E_up  = m_R g0 h_up / (η_up * 3.6e6)       MODEL_ASSUMPTION_ACCEPTED
E_down = 0
E_setup = (P_hover + P_comm) * T_setup / 3600   MODEL_DERIVED
E_service = (P_hover + P_comm) * T_service / 3600
E_R = E_out + E_setup + E_service + E_back
M_E_R = (1-ρ_R) E_use − E_R ≥ 0
```

## Coverage requirement (strict)

For atomic task k and fixed site r over interval I_k:

```text
min_t min(M_TR(t,r), M_RG(r)) ≥ 0   (Gamma_C = 0 this stage)
```

Partial coverage is **not** feasible — must split the gap in time.

## Timing (not a structural reject)

`T_ready = T_prep + T_out + T_setup`.  
If `T_ready > task_start` record `required_transport_shift`; **do not delete** the site (Q3 may shift transport starts later).

## Split / merge

- Prefer spatial refine then height refine before time split.
- Binary time split; `MIN_ATOMIC_DURATION=2 s`, `MAX_SPLIT_DEPTH=10`.
- If still empty at 30 m / 25 m grid: `GRID_UNRESOLVED` (not “impossible”).
- After split, merge-back if adjacent tasks share a common feasible site.

## E5 exclusions

No R01/R02 assignment, no energy-pack scheduling, no task merge across parents, no transport time-shift application, no Q3 ALNS/SOCP/Γ_C scan/ns-3/Q4.
