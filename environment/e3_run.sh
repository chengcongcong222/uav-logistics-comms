#!/usr/bin/env bash
set -euo pipefail
cd /home/ccc/projects/uav-logistics-comms
mkdir -p results/q2
{
  echo "==== hygiene ===="
  bash environment/check_repo_hygiene.sh
  echo "==== solve_q2 ===="
  .venv/bin/python -m src.q2.solve_q2
  echo "==== export ===="
  .venv/bin/python -m src.q2.export_submission
  echo "==== validate ===="
  .venv/bin/python validation/mathematical/e3_validate_q2.py
  echo "E3_DONE"
} > results/q2/e3_run.log 2>&1
echo EXIT:$?
tail -n 80 results/q2/e3_run.log
