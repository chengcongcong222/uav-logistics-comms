# DATA_CONTRACT

Units and provenance for all model inputs/outputs. Every later stage must cite this contract.

## Global conventions

| Topic | Rule |
| --- | --- |
| Time | seconds (`s`) |
| Length | meters (`m`) |
| Mass | kilograms (`kg`) |
| Volume | cubic meters (`m³`) |
| Energy | kilowatt-hours (`kWh`) for storage/mission energy; kW for power |
| Power | kilowatts (`kW`) |
| Angle / geo | longitude/latitude in degrees (WGS84 / EPSG:4326), kept immutable |
| Plane coordinates | WGS84 / UTM zone 49N (EPSG:32649): `x_m`, `y_m` |
| SOC | fraction 0–1 internally; source tables may use percent |
| Missing values | empty CSV cell or JSON `null`; never invent 0 for unknown |
| Naming convention | `is_*` flags are booleans; IDs are strings |

## Provenance tags

- `SOURCE_GIVEN`: present in raw workbook/DEM/problem statement
- `SOURCE_DERIVED`: computed from source fields with a documented formula
- `ASSUMPTION_REQUIRED`: project convention when the statement is silent (must be labeled)

## `nodes.csv`

| field | unit | source | notes |
| --- | --- | --- | --- |
| node_id | - | SOURCE_GIVEN | `O01`, `S001`–`S015` |
| node_name | - | SOURCE_GIVEN | |
| node_type | - | SOURCE_DERIVED | `dispatch_center` / `service_area` |
| longitude | deg | SOURCE_GIVEN | EPSG:4326 |
| latitude | deg | SOURCE_GIVEN | EPSG:4326 |
| ground_elevation_m | m | SOURCE_GIVEN | attachment elevation |
| population | persons | SOURCE_GIVEN | service areas only |
| x_m, y_m | m | SOURCE_DERIVED | EPSG:32649 |
| epsg_lonlat / epsg_plane | - | SOURCE_DERIVED | 4326 / 32649 |
| utm49n_valid | bool | SOURCE_DERIVED | lon∈[108,114], lat∈[0,84] |

## `transport_uav_types.csv`

All parameters SOURCE_GIVEN from `运输无人机数据.xlsx`.

| field | unit |
| --- | --- |
| empty_mass_with_battery_kg | kg |
| max_payload_kg | kg |
| cargo_volume_m3 | m³ |
| cruise_speed_mps | m/s |
| range_empty_m / range_full_m | m |
| battery_energy_kwh | kWh |
| return_soc_min_pct | % |
| prep_time_s / load_time_per_box_s | s |
| handover_base_s / handover_per_box_s | s |
| max_climb_mps / max_descend_mps | m/s |
| climb_energy_eff / descend_energy_eff | - |

## `transport_uavs.csv`

`uav_id`, `uav_type`, `home_node_id` — SOURCE_GIVEN.

## `transport_batteries.csv`

`uav_type`, `battery_pool_count`, `full_charge_time_s` — SOURCE_GIVEN.

## `relay_uav_types.csv`, `relay_uavs.csv`, `relay_energy_components.csv`

SOURCE_GIVEN from `中继无人机数据.xlsx` (hover/comm power, energy pools, etc.).

## `boxes.csv`

Source sheet `逐箱货箱清单` is SOURCE_GIVEN (already one row per physical box).

| field | unit | notes |
| --- | --- | --- |
| box_id | - | SOURCE_GIVEN e.g. `S001-MED-01` |
| service_id | - | SOURCE_GIVEN |
| material_type | - | SOURCE_GIVEN |
| mass_kg / volume_m3 | kg / m³ | SOURCE_GIVEN |
| is_first_batch | bool | SOURCE_GIVEN (`是`/`否`) |
| is_medical | bool | SOURCE_DERIVED |
| first_deadline_s | s | SOURCE_GIVEN, empty if not first-batch |
| expected_deadline_s | s | SOURCE_GIVEN |
| priority_weight | - | SOURCE_GIVEN `应急优先系数` |

**Convention note:** if a future rebuild expands boxes from the summary sheet and the statement does not define numbering, box indices within `(service, material)` are `ASSUMPTION_REQUIRED`. Current pipeline uses the given per-box sheet and does not invent IDs.

## `communication_parameters.json`

SOURCE_GIVEN from `通信链路参数.xlsx` (frequency, losses, sensitivity, Tx/Rx antenna params).

## DEM (`dem_metadata.json`)

| item | rule |
| --- | --- |
| CRS | SOURCE_GIVEN EPSG:4326 |
| Grid | SOURCE_GIVEN 1309 rows × 1486 cols |
| Resolution | SOURCE_GIVEN ~0.000277…° (~30 m) |
| Orientation | SOURCE_DERIVED: row 0 = north (latitude descending) |
| MAT vs TIF | SOURCE_DERIVED consistent (same shape and elev range) |
| Sampling | nearest cell via affine transform at lon/lat |

## Elevation cross-check

`results/e1/node_dem_elevation_check.csv` records `difference_m = given − dem`. Differences are reported, not forced equal. Coordinate/index errors large enough to indicate misalignment block the gate.

## Route geometry (E2)

Planned cruise altitude along a leg:

```text
planned_cruise_altitude_m = max_dem_elevation_along_leg + 50
```

Operation altitudes (SOURCE_GIVEN rule):

- O01: ground elevation
- Service area: ground elevation + 30 m
