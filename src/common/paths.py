"""Project path constants."""
from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path("/home/ccc/projects/uav-logistics-comms")
RAW_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
CACHE_DIR = PROJECT_ROOT / "data" / "cache"
EXPORT_DIR = PROJECT_ROOT / "export"
RESULTS_DIR = PROJECT_ROOT / "results"
RESULTS_E1 = RESULTS_DIR / "e1"
RESULTS_E2 = RESULTS_DIR / "e2"
RESULTS_Q1 = RESULTS_DIR / "q1"
DOCS_MODEL = PROJECT_ROOT / "docs" / "model"

RAW_BASE = RAW_DIR / "数据" / "无人机应急物资运输基础数据"
RAW_GEO = RAW_DIR / "数据" / "镇龙乡地理空间数据" / "镇龙乡及周边地理数据"
DEM_DIR = RAW_GEO / "数字高程模型数据（DEM）"

XLSX_NODES = RAW_BASE / "调度中心与服务区.xlsx"
XLSX_TRANSPORT = RAW_BASE / "运输无人机数据.xlsx"
XLSX_RELAY = RAW_BASE / "中继无人机数据.xlsx"
XLSX_DEMAND = RAW_BASE / "物资需求与配送时限.xlsx"
XLSX_COMM = RAW_BASE / "通信链路参数.xlsx"
DEM_MAT = DEM_DIR / "镇龙乡及周边30米DEM.mat"
DEM_TIF = DEM_DIR / "镇龙乡及周边30米DEM.tif"

for _d in (PROCESSED_DIR, CACHE_DIR, EXPORT_DIR, RESULTS_E1, RESULTS_E2, RESULTS_Q1, DOCS_MODEL):
    _d.mkdir(parents=True, exist_ok=True)
