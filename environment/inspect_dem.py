#!/usr/bin/env python3
from pathlib import Path
import rasterio
from scipy.io import loadmat
import numpy as np

ROOT = Path("/home/ccc/projects/uav-logistics-comms")
DEM_DIR = ROOT / "data/raw/数据/镇龙乡地理空间数据/镇龙乡及周边地理数据/数字高程模型数据（DEM）"
tif = DEM_DIR / "镇龙乡及周边30米DEM.tif"
mat = DEM_DIR / "镇龙乡及周边30米DEM.mat"

with rasterio.open(tif) as ds:
    print("TIF crs", ds.crs)
    print("TIF transform", ds.transform)
    print("TIF bounds", ds.bounds)
    print("TIF size", ds.width, ds.height)
    print("TIF nodata", ds.nodata)
    arr = ds.read(1)
    print("elev min/max", float(np.nanmin(arr)), float(np.nanmax(arr)))

raw = loadmat(mat)
print("MAT keys", [k for k in raw if not k.startswith("__")])
for k, v in raw.items():
    if k.startswith("__"):
        continue
    a = np.asarray(v)
    print(k, a.shape, a.dtype, a.ravel()[:8])
