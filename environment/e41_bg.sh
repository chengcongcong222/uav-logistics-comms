#!/usr/bin/env bash
set -euo pipefail
cd /home/ccc/projects/uav-logistics-comms
nohup .venv/bin/python -u -m src.q3.analyze_e41 > results/q3/e41_run.log 2>&1 &
echo PID=$!
sleep 3
head -n 15 results/q3/e41_run.log
