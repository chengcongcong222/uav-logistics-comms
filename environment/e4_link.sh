#!/usr/bin/env bash
set -euo pipefail
cd /home/ccc/projects/uav-logistics-comms
.venv/bin/python -m src.q3.link_budget > results/q3_link.log 2>&1
echo EXIT:$?
cat results/q3_link.log
