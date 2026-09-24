#!/usr/bin/env bash
set -euo pipefail
cd /home/ccc/projects/uav-logistics-comms
{
  echo "==== e32 pareto ===="
  .venv/bin/python validation/mathematical/e32_validate_pareto.py
  echo "==== e32 schedules ===="
  .venv/bin/python validation/mathematical/e32_validate_pareto_schedules.py
  echo "==== link budget ===="
  .venv/bin/python validation/mathematical/e4_validate_link_budget.py
  echo "==== los ===="
  .venv/bin/python validation/mathematical/e4_validate_los.py
  echo "==== e41 gaps ===="
  .venv/bin/python validation/mathematical/e41_validate_gaps.py
  echo "==== report ===="
  .venv/bin/python validation/mathematical/e41_validate_report.py
  echo "==== burden ===="
  cat results/q3/q2_pareto_communication_burden.csv
  echo "==== pareto ===="
  cat results/q2/q2_pareto_e32.csv
  echo "E32_E41_VALIDATION_DONE"
} > results/q3/e32_e41_validate.log 2>&1
echo EXIT:$?
cat results/q3/e32_e41_validate.log
