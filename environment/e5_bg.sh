#!/usr/bin/env bash
set -euo pipefail
cd /home/ccc/projects/uav-logistics-comms
nohup .venv/bin/python -u -m src.q3.e5_relay_tasks > results/q3/e5_run.log 2>&1 &
echo PID=$!
sleep 3
head -n 20 results/q3/e5_run.log
