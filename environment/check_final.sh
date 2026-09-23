#!/usr/bin/env bash
set -euo pipefail
LOG=/home/ccc/projects/uav-logistics-comms/environment/ns3_test.log
echo "==== last lines of ns3_test.log ===="
tail -n 30 "$LOG"
echo "==== fail scan ===="
if grep -E 'FAIL|CRASH' "$LOG"; then
  echo HAS_FAIL
else
  echo NO_FAIL
fi
echo "==== pass summary ===="
grep -E 'tests passed' "$LOG" || true
echo "==== first log ===="
cat /home/ccc/projects/uav-logistics-comms/environment/ns3_first.log
echo "==== smoke ===="
cat /home/ccc/projects/uav-logistics-comms/results/ns3/e0_smoke_summary.csv
