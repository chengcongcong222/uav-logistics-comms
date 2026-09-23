#!/usr/bin/env bash
set -euo pipefail
PROJECT_ROOT="/home/ccc/projects/uav-logistics-comms"
NS3_DIR="$PROJECT_ROOT/external/ns-3.47"
SCRATCH="$NS3_DIR/scratch"
RESULTS="$PROJECT_ROOT/results/ns3"
ENV_DIR="$PROJECT_ROOT/environment"

mkdir -p "$SCRATCH" "$RESULTS" "$PROJECT_ROOT/export"

# Python smoke + trace generation
source "$PROJECT_ROOT/.venv/bin/activate"
python "$PROJECT_ROOT/validation/mathematical/e0_python_smoke.py" 2>&1 | tee "$ENV_DIR/python_smoke.log"
python "$PROJECT_ROOT/validation/mathematical/e0_generate_trace.py" 2>&1 | tee "$ENV_DIR/trace_gen.log"

# Install smoke source into ns-3 scratch (do not modify unrelated official sources)
cp -f "$PROJECT_ROOT/validation/ns3/e0-smoke.cc" "$SCRATCH/e0-smoke.cc"

cd "$NS3_DIR"
./ns3 build e0-smoke 2>&1 | tee "$ENV_DIR/e0_smoke_build.log"
./ns3 run "e0-smoke --trace=$PROJECT_ROOT/export/e0_test_trace.csv --summary=$RESULTS/e0_smoke_summary.csv --simTime=25" 2>&1 | tee "$ENV_DIR/e0_smoke_run.log"

echo "==== summary csv ===="
cat "$RESULTS/e0_smoke_summary.csv"

# Acceptance checks
python - <<'PY'
from pathlib import Path
import csv
root = Path("/home/ccc/projects/uav-logistics-comms")
summary = root / "results" / "ns3" / "e0_smoke_summary.csv"
assert summary.exists(), "missing summary csv"
row = next(csv.DictReader(summary.open()))
tx = int(row["tx_packets"])
rx = int(row["rx_packets"])
pdr = float(row["pdr"])
print("ACCEPTANCE")
print(f"tx_packets={tx}")
print(f"rx_packets={rx}")
print(f"pdr={pdr}")
assert tx > 0, "tx_packets must be > 0"
assert rx > 0, "rx_packets must be > 0"
assert pdr > 0, "pdr must be > 0"
print("SMOKE_ACCEPTANCE_OK")
PY

echo "E0_SMOKE_DONE"
