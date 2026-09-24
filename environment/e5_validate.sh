#!/usr/bin/env bash
set -euo pipefail
cd /home/ccc/projects/uav-logistics-comms
{
  echo "==== validate candidates ===="
  .venv/bin/python validation/mathematical/e5_validate_relay_candidates.py
  echo "==== validate energy ===="
  .venv/bin/python validation/mathematical/e5_validate_relay_energy.py
  echo "==== validate atomic ===="
  .venv/bin/python validation/mathematical/e5_validate_atomic_tasks.py
  echo "==== summary ===="
  cat results/q3/relay_task_summary.csv
  echo "==== unresolved ===="
  cat results/q3/relay_unresolved.csv
  echo "E5_VALIDATE_DONE"
} > results/q3/e5_validate.log 2>&1
echo EXIT:$?
cat results/q3/e5_validate.log
