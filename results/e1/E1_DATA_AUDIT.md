# E1 Data Audit

## Decision

**E1_DATA_READY**

## Hygiene precheck

`check_repo_hygiene.sh` → `REPO_HYGIENE_OK`, `RAW_DATA_UNCHANGED`

## Fact checks (all PASS)

| fact | expected | actual |
| --- | --- | --- |
| dispatch centers | 1 | 1 |
| service areas | 15 | 15 |
| boxes | 80 | 80 |
| transport UAVs | 8 | 8 |
| type A / B / C | 4 / 2 / 2 | 4 / 2 / 2 |
| relay UAVs | 2 | 2 |
| batteries A / B / C | 6 / 4 / 4 | 6 / 4 / 4 |
| relay energy components | 6 | 6 |
| first-batch boxes | 30 | 30 |
| total mass | 758 kg | 758 kg |
| total volume | 2.011 m³ | 2.011 m³ |
| medical | 16 / 48 / 0.192 | match |
| drinking water | 36 / 504 / 0.972 | match |
| food | 19 / 152 / 0.532 | match |
| hygiene | 9 / 54 / 0.315 | match |

## Box expansion

Raw workbook already contains sheet `逐箱货箱清单` with 80 physical boxes (SOURCE_GIVEN IDs). No invented renumbering.

## DEM audit

| item | value |
| --- | --- |
| CRS | EPSG:4326 |
| size | 1309 rows × 1486 cols |
| resolution | 0.000278° (~30 m) |
| elev min/max | 41.689 / 1132.856 m |
| NoData | TIF none; MAT marks -32767 |
| orientation | row0 = north |
| MAT vs TIF | shape + elev range consistent |

Artifacts: `data/processed/dem_metadata.json`, `results/e1/dem_audit.csv`

## Coordinates

All 16 nodes inside UTM 49N validity (108–114°E). Lon/lat kept; `x_m,y_m` derived as EPSG:32649.

## Node elevation cross-check

`results/e1/node_dem_elevation_check.csv`

- mean |given − DEM| ≈ 3.55 m
- max |given − DEM| ≈ 10.56 m
- No coordinate/index-scale error; differences treated as source vs DEM resolution/definition gap, not forced equal.

## Outputs

- `data/processed/nodes.csv`
- `data/processed/transport_uav_types.csv`
- `data/processed/transport_uavs.csv`
- `data/processed/transport_batteries.csv`
- `data/processed/relay_uav_types.csv`
- `data/processed/relay_uavs.csv`
- `data/processed/relay_energy_components.csv`
- `data/processed/boxes.csv`
- `data/processed/communication_parameters.json`
- `docs/model/DATA_CONTRACT.md`
- `validation/mathematical/e1_validate_data.py` → `E1_DATA_VALIDATION_OK`

## Next

E2 formula audit → shared physics → Q1 baseline.
