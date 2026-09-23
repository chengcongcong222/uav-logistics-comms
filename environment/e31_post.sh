#!/usr/bin/env bash
set -euo pipefail
cd /home/ccc/projects/uav-logistics-comms
{
  echo "==== export submission ===="
  .venv/bin/python -m src.q2.export_submission
  echo "==== export trace ===="
  .venv/bin/python -m src.q2.export_trace
  echo "==== e3_validate_q2 ===="
  .venv/bin/python validation/mathematical/e3_validate_q2.py
  echo "==== e3_validate_trace ===="
  .venv/bin/python validation/mathematical/e3_validate_trace.py
  echo "==== e3_validate_pareto ===="
  .venv/bin/python validation/mathematical/e3_validate_pareto.py
  echo "==== hygiene ===="
  bash environment/check_repo_hygiene.sh
  echo "==== key files ===="
  cat results/q2/candidate_gate_totals.csv
  echo
  cat results/q2/baseline_comparison.csv
  echo
  cat results/q2/q2_pareto.csv
  echo "E31_POST_DONE"
} > results/q2/e31_post.log 2>&1
echo EXIT:$?
cat results/q2/e31_post.log
