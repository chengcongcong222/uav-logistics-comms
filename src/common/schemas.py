"""Standard field names and unit conventions (see docs/model/DATA_CONTRACT.md)."""
from __future__ import annotations

# Material types
MATERIAL_MED = "医疗物资"
MATERIAL_WAT = "饮用水"
MATERIAL_FOD = "应急食品"
MATERIAL_HYG = "生活卫生用品"
MATERIAL_TYPES = [MATERIAL_MED, MATERIAL_WAT, MATERIAL_FOD, MATERIAL_HYG]

# UTM zone used for local plane coordinates
EPSG_WGS84 = 4326
EPSG_UTM49N = 32649

# Operation altitude rules (from problem statement)
CRUISE_MARGIN_ABOVE_MAX_DEM_M = 50.0
SERVICE_OPERATION_AGL_M = 30.0
ORIGIN_OPERATION_AGL_M = 0.0
