#!/usr/bin/env bash
set -euo pipefail
cd /home/ccc/projects/uav-logistics-comms
pkill -9 -f recover_eps_points || true
sleep 1
nohup .venv/bin/python -u -m src.q3.recover_eps_points > results/q3/e4_eps_recover.log 2>&1 &
echo PID=$!
sleep 5
cat results/q3/e4_eps_recover.log
