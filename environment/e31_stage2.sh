#!/usr/bin/env bash
set -euo pipefail
cd /home/ccc/projects/uav-logistics-comms
nohup .venv/bin/python -u -m src.q2.solve_q2_stage2 > results/q2/solve_q2_stage2.log 2>&1 &
echo "PID=$!"
sleep 3
cat results/q2/solve_q2_stage2.log
