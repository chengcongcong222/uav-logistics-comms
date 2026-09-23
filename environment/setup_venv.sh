#!/usr/bin/env bash
set -euo pipefail
PROJECT_ROOT="/home/ccc/projects/huawei-cup-d"
cd "$PROJECT_ROOT"
if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
python -m pip install numpy scipy pandas openpyxl matplotlib rasterio pyproj
python -m pip freeze > environment/requirements.txt
python -c "import numpy,scipy,pandas,openpyxl,matplotlib,rasterio,pyproj; print('imports_ok')"
python --version
which python
