#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "==== repo hygiene ===="
bash environment/check_repo_hygiene.sh

echo "==== last lines of ns3_test.log ===="
tail -n 30 environment/ns3_test.log
echo "==== fail scan ===="
if grep -E 'FAIL|CRASH' environment/ns3_test.log; then
  echo HAS_FAIL
else
  echo NO_FAIL
fi
echo "==== pass summary ===="
grep -E 'tests passed' environment/ns3_test.log || true
echo "==== first log ===="
cat environment/ns3_first.log
echo "==== smoke ===="
cat results/ns3/e0_smoke_summary.csv
