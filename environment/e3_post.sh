#!/usr/bin/env bash
set -euo pipefail
cd /home/ccc/projects/uav-logistics-comms
{
  echo "==== export ===="
  .venv/bin/python -m src.q2.export_submission
  echo "==== validate ===="
  .venv/bin/python validation/mathematical/e3_validate_q2.py
  echo "==== trace ===="
  .venv/bin/python -m src.q2.export_trace
  echo "==== hygiene ===="
  bash environment/check_repo_hygiene.sh
  echo "E3_POST_DONE"
} > results/q2/e3_post.log 2>&1
echo EXIT:$?
cat results/q2/e3_post.log
