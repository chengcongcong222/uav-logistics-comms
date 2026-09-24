#!/usr/bin/env bash
set -euo pipefail
cd /home/ccc/projects/uav-logistics-comms
nohup .venv/bin/python -u -m src.q2.e32_reaudit > results/q2/e32_run.log 2>&1 &
echo PID=$!
sleep 3
head -n 20 results/q2/e32_run.log
