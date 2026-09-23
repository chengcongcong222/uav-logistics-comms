"""E1 data loader: parse five workbooks into standard tables."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from .coordinates import lonlat_to_utm49n, utm49n_valid
from .excel_io import load_sheet_frame, sheet_values
from .paths import (
    PROCESSED_DIR,
    XLSX_COMM,
    XLSX_DEMAND,
    XLSX_NODES,
    XLSX_RELAY,
    XLSX_TRANSPORT,
)
from .schemas import EPSG_UTM49N, EPSG_WGS84


def load_nodes() -> pd.DataFrame:
    rows = sheet_values(XLSX_NODES, "数据")
    records = []
    # dispatch center: row 3 (index 2)
    r = rows[2]
    records.append(
        {
            "node_id": r[0],
            "node_name": r[1],
            "node_type": "dispatch_center",
            "longitude": float(r[2]),
            "latitude": float(r[3]),
            "ground_elevation_m": float(r[4]),
            "population": None,
        }
    )
    # services start at row 7 (index 6)
    for r in rows[6:]:
        if not r or r[0] is None:
            continue
        records.append(
            {
                "node_id": r[0],
                "node_name": r[1],
                "node_type": "service_area",
                "longitude": float(r[2]),
                "latitude": float(r[3]),
                "ground_elevation_m": float(r[4]),
                "population": int(r[5]) if r[5] is not None else None,
            }
        )
    df = pd.DataFrame(records)
    coords = [lonlat_to_utm49n(lon, lat) for lon, lat in zip(df["longitude"], df["latitude"])]
    df["x_m"] = [c[0] for c in coords]
    df["y_m"] = [c[1] for c in coords]
    df["epsg_lonlat"] = EPSG_WGS84
    df["epsg_plane"] = EPSG_UTM49N
    df["utm49n_valid"] = [
        utm49n_valid(lon, lat) for lon, lat in zip(df["longitude"], df["latitude"])
    ]
    return df


def load_transport_types() -> pd.DataFrame:
    rows = sheet_values(XLSX_TRANSPORT, "数据")
    header = rows[1]
    recs = []
    for r in rows[2:5]:
        recs.append(
            {
                "uav_type": r[0],
                "type_name": r[1],
                "empty_mass_with_battery_kg": float(r[2]),
                "max_payload_kg": float(r[3]),
                "cargo_volume_m3": float(r[4]),
                "cruise_speed_mps": float(r[5]),
                "range_empty_m": float(r[6]),
                "range_full_m": float(r[7]),
                "battery_energy_kwh": float(r[8]),
                "return_soc_min_pct": float(r[9]),
                "prep_time_s": float(r[10]),
                "load_time_per_box_s": float(r[11]),
                "handover_base_s": float(r[12]),
                "handover_per_box_s": float(r[13]),
                "max_climb_mps": float(r[14]),
                "max_descend_mps": float(r[15]),
                "climb_energy_eff": float(r[16]),
                "descend_energy_eff": float(r[17]),
            }
        )
    return pd.DataFrame(recs)


def load_transport_uavs() -> pd.DataFrame:
    rows = sheet_values(XLSX_TRANSPORT, "数据")
    recs = []
    for r in rows:
        if not r or r[0] is None:
            continue
        if str(r[0]).startswith("U") and r[1] in ("A", "B", "C"):
            recs.append({"uav_id": r[0], "uav_type": r[1], "home_node_id": r[2]})
    return pd.DataFrame(recs)


def load_transport_batteries() -> pd.DataFrame:
    rows = sheet_values(XLSX_TRANSPORT, "数据")
    recs = []
    for r in rows:
        if not r or r[0] is None or r[1] is None:
            continue
        if str(r[0]) in ("A", "B", "C") and isinstance(r[1], (int, float)) and not isinstance(r[1], bool):
            # type parameter rows have many numeric fields; battery rows have exactly 3 used cols
            if r[2] is not None and (r[3] is None):
                recs.append(
                    {
                        "uav_type": r[0],
                        "battery_pool_count": int(r[1]),
                        "full_charge_time_s": float(r[2]),
                    }
                )
    return pd.DataFrame(recs)


def load_relay_types_and_uavs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rows = sheet_values(XLSX_RELAY, "数据")
    r0 = rows[2]
    types = pd.DataFrame(
        [
            {
                "relay_type": r0[0],
                "type_name": r0[1],
                "empty_mass_with_energy_kg": float(r0[2]),
                "comm_module_mass_kg": float(r0[3]),
                "takeoff_mass_kg": float(r0[4]),
                "cruise_speed_mps": float(r0[5]),
                "cruise_power_kw": float(r0[6]),
                "energy_kwh": float(r0[7]),
                "return_soc_min_pct": float(r0[8]),
                "prep_time_s": float(r0[9]),
                "link_setup_time_s": float(r0[10]),
                "turnaround_time_s": float(r0[11]),
                "max_climb_mps": float(r0[12]),
                "max_descend_mps": float(r0[13]),
                "climb_energy_eff": float(r0[14]),
                "descend_energy_eff": float(r0[15]),
                "hover_power_kw": float(r0[16]),
                "comm_power_kw": float(r0[17]),
                "max_hover_agl_m": float(r0[18]),
            }
        ]
    )
    uavs = []
    for r in rows:
        if not r or r[0] is None:
            continue
        if str(r[0]).startswith("R") and r[1] == "R":
            uavs.append({"relay_id": r[0], "relay_type": r[1], "home_node_id": r[2]})
    energy = []
    for r in rows:
        if not r or r[0] is None or r[1] is None:
            continue
        if str(r[0]) == "R" and isinstance(r[1], (int, float)) and r[2] is not None and r[3] is None:
            energy.append(
                {
                    "relay_type": r[0],
                    "energy_pool_count": int(r[1]),
                    "full_charge_time_s": float(r[2]),
                }
            )
    return types, pd.DataFrame(uavs), pd.DataFrame(energy)


def load_boxes() -> pd.DataFrame:
    df = load_sheet_frame(XLSX_DEMAND, "逐箱货箱清单", header_row=1)
    rename = {
        "货箱编号": "box_id",
        "服务区编号": "service_id",
        "物资类型": "material_type",
        "单箱质量（kg）": "mass_kg",
        "单箱体积（m³）": "volume_m3",
        "是否首批保障": "is_first_batch",
        "首批截止时间（s）": "first_deadline_s",
        "期望送达时间（s）": "expected_deadline_s",
        "应急优先系数": "priority_weight",
    }
    df = df.rename(columns=rename)
    df["is_first_batch"] = df["is_first_batch"].map({"是": True, "否": False, True: True, False: False})
    df["is_medical"] = df["material_type"] == "医疗物资"
    df["mass_kg"] = df["mass_kg"].astype(float)
    df["volume_m3"] = df["volume_m3"].astype(float)
    df["priority_weight"] = df["priority_weight"].astype(float)
    for c in ("first_deadline_s", "expected_deadline_s"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df[
        [
            "box_id",
            "service_id",
            "material_type",
            "mass_kg",
            "volume_m3",
            "is_first_batch",
            "is_medical",
            "first_deadline_s",
            "expected_deadline_s",
            "priority_weight",
        ]
    ]


def load_demand_summary() -> pd.DataFrame:
    df = load_sheet_frame(XLSX_DEMAND, "数据", header_row=1)
    rename = {
        "服务区编号": "service_id",
        "物资类型": "material_type",
        "总需求箱数": "total_boxes",
        "首批必须送达箱数": "first_batch_boxes",
        "单箱质量（kg）": "mass_kg",
        "单箱体积（m³）": "volume_m3",
        "应急优先系数": "priority_weight",
        "首批截止时间（s）": "first_deadline_s",
        "期望送达时间（s）": "expected_deadline_s",
    }
    return df.rename(columns=rename)


def load_comm_params() -> dict:
    rows = sheet_values(XLSX_COMM, "数据")
    out: dict = {"endpoints": {}, "propagation": {}, "receiver": {}}
    for r in rows[2:]:
        if not r or r[0] is None:
            continue
        cat, name, _sym, val = r[0], r[1], r[3], r[4]
        entry = {"name": name, "value": float(val)}
        if cat == "传播参数":
            out["propagation"][str(name)] = entry
        elif cat == "接收参数":
            out["receiver"][str(name)] = entry
        else:
            out["endpoints"].setdefault(str(cat), {})[str(name)] = entry
    return out


def write_processed() -> dict[str, Path]:
    nodes = load_nodes()
    types = load_transport_types()
    uavs = load_transport_uavs()
    batteries = load_transport_batteries()
    relay_types, relay_uavs, relay_energy = load_relay_types_and_uavs()
    boxes = load_boxes()
    comm = load_comm_params()

    paths = {
        "nodes": PROCESSED_DIR / "nodes.csv",
        "transport_uav_types": PROCESSED_DIR / "transport_uav_types.csv",
        "transport_uavs": PROCESSED_DIR / "transport_uavs.csv",
        "transport_batteries": PROCESSED_DIR / "transport_batteries.csv",
        "relay_uav_types": PROCESSED_DIR / "relay_uav_types.csv",
        "relay_uavs": PROCESSED_DIR / "relay_uavs.csv",
        "relay_energy_components": PROCESSED_DIR / "relay_energy_components.csv",
        "boxes": PROCESSED_DIR / "boxes.csv",
        "communication_parameters": PROCESSED_DIR / "communication_parameters.json",
    }
    nodes.to_csv(paths["nodes"], index=False)
    types.to_csv(paths["transport_uav_types"], index=False)
    uavs.to_csv(paths["transport_uavs"], index=False)
    batteries.to_csv(paths["transport_batteries"], index=False)
    relay_types.to_csv(paths["relay_uav_types"], index=False)
    relay_uavs.to_csv(paths["relay_uavs"], index=False)
    relay_energy.to_csv(paths["relay_energy_components"], index=False)
    boxes.to_csv(paths["boxes"], index=False)
    paths["communication_parameters"].write_text(
        json.dumps(comm, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return paths
