#!/usr/bin/env bash
set -euo pipefail
cd /home/ccc/projects/uav-logistics-comms
mkdir -p results/q3 results/q2/pareto_schedules
nohup bash -c '.venv/bin/python -m src.q3.link_budget && .venv/bin/python -u -m src.q3.recover_pareto_schedules' > results/q3/e4_recover.log 2>&1 &
echo PID=$!
sleep 2
tail -n 15 results/q3/e4_recover.log || true
