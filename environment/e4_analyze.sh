#!/usr/bin/env bash
set -euo pipefail
cd /home/ccc/projects/uav-logistics-comms
{
  echo "==== analyze pareto comm ===="
  .venv/bin/python -u -m src.q3.analyze_q2_pareto
  echo "==== link budget validate ===="
  .venv/bin/python validation/mathematical/e4_validate_link_budget.py
  echo "==== los validate ===="
  .venv/bin/python validation/mathematical/e4_validate_los.py
  echo "==== gaps validate ===="
  .venv/bin/python validation/mathematical/e4_validate_gaps.py
  echo "==== relay unit ===="
  .venv/bin/python validation/mathematical/e4_relay_unit.py
  echo "==== hygiene ===="
  bash environment/check_repo_hygiene.sh
  echo "==== burden ===="
  cat results/q3/q2_pareto_communication_burden.csv
  echo "E4_ALL_DONE"
} > results/q3/e4_analyze.log 2>&1
echo EXIT:$?
cat results/q3/e4_analyze.log
