# Q3_COMMUNICATION_SEMANTICS

Frozen Q3 communication interpretation (E4). Physics formulas remain those in MODEL_FREEZE / FORMULA_AUDIT.

## Activity interval

Transport UAV must maintain communication from **takeoff** to **return_O01** inclusive of:

- climb, cruise, descent, handover, return flight

**Not** checked: prep/load at O01.

(`SOURCE_GIVEN` problem text: continuous comm during climb/cruise/descent/handover.)

## Priority / topology

At any time:

1. If **transport ↔ G01 direct** is available (`M_C ≥ 0`) → use direct.
2. Else **at most one relay** may assist: `transport ↔ relay ↔ G01`.
3. **Relay–relay multihop prohibited**.

E4 identifies direct availability and computes two-hop margins for a *given* relay position. No relay assignment.

## Link budget (`SOURCE_GIVEN` formulas)

```text
Lmax(a→b) = Pt_a + Gt_a + Gr_b − L_sys − (P_sens,b + M)
Lmax(a↔b) = min(Lmax(a→b), Lmax(b→a))
FSPL = 32.45 + 20 log10(f_MHz) + 20 log10(D_km)
L_path = FSPL + L_obs · b
M_C = Lmax − L_path
```

`b ∈ {0,1}` terrain obstruction. Parameters from `data/processed/communication_parameters.json` (not hardcoded).

## Endpoints

| node | position |
| --- | --- |
| G01 | O01 lon/lat/x/y, **z = O01 ground + hG (20 m AGL)** |
| transport | trace `(x,y,z)` AMSL — do **not** add ground again |
| relay | `(x,y,z)` AMSL; AGL = z − DEM(ground) |

## Terrain obstruction (`MODEL_DERIVED` operationalization)

Segment A–B, open interval λ∈(0,1):

```text
z_LOS(λ) = (1−λ) zA + λ zB
```

If any interior DEM sample has `z_DEM ≥ z_LOS` → `b=1`, else `b=0`.

Rules:

- ignore endpoint cells (no self-occlusion)
- ignore NoData cells
- clip to DEM bounds; out-of-bounds horizontal → treat as blocked (`b=1`) and log
- duplicate raster cells along the line are checked once

Two independent implementations: raster line traversal (primary) vs dense sampling ≤10 m (validator). Random 1000 3D pairs for cross-check.

## Continuous margin sampling

No coarse fixed 10 s / 100 m grid as the sole check.

- every phase start/end and handover interval endpoints included
- flight segments subdivided: horizontal step ≤ 15 m, vertical step ≤ 5 m
- binary refine where `sign(M_C)` or LOS state changes until boundary time error ≤ 0.1 s
- handover: fixed position; margin constant over `[handover_start, handover_end]` (full interval)

## Gaps

```text
I_p = { t : M_C_direct(t) < 0 }  on [takeoff, return]
```

Maximal closed intervals → gap records with cause:

| cause | rule |
| --- | --- |
| DISTANCE_ONLY | `M_C_LOS < 0` (b=0) |
| TERRAIN_BLOCKAGE | `M_C_LOS ≥ 0` and `M_C < 0` |
| DISTANCE_AND_BLOCKAGE | both |

## Relay margins (functions only; no scheduling)

```text
M_UR(t) = margin(transport(t) ↔ relay)
M_RG    = margin(relay ↔ G01)
M_relay(t) = min(M_UR(t), M_RG)
```

Relay position legality (E4): inside DEM, 0 ≤ AGL ≤ 300 m.

## Out of scope in E4

Relay placement optimization, R01/R02 assignment, energy packs, relay merging, transport time-shift, Q3 ALNS, SOCP, ns-3 formal runs, Q4.
