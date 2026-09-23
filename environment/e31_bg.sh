#!/usr/bin/env bash
set -euo pipefail
cd /home/ccc/projects/uav-logistics-comms
mkdir -p results/q2
nohup .venv/bin/python -u -m src.q2.solve_q2 > results/q2/solve_q2_e31.log 2>&1 &
echo "PID=$!"
sleep 2
head -n 15 results/q2/solve_q2_e31.log || true
