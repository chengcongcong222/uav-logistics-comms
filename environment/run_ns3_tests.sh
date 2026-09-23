#!/usr/bin/env bash
set -euo pipefail
PROJECT_ROOT="/home/ccc/projects/huawei-cup-d"
NS3_DIR="$PROJECT_ROOT/external/ns-3.47"
ENV_DIR="$PROJECT_ROOT/environment"
cd "$NS3_DIR"

echo "==== ./test.py ===="
./test.py 2>&1 | tee "$ENV_DIR/ns3_test.log"
echo "==== test.py finished, scanning for FAIL ===="
if grep -E 'FAIL|CRASH' "$ENV_DIR/ns3_test.log"; then
  echo "FAIL_FOUND"
  # still continue to collect first example, but exit code will reflect
  TEST_FAIL=1
else
  echo "NO_FAIL"
  TEST_FAIL=0
fi

echo "==== ./ns3 run first ===="
./ns3 run first 2>&1 | tee "$ENV_DIR/ns3_first.log"
if grep -qiE 'assert|error|abort' "$ENV_DIR/ns3_first.log"; then
  echo "FIRST_MAY_HAVE_ISSUES"
else
  echo "FIRST_OK"
fi

if [[ "$TEST_FAIL" -ne 0 ]]; then
  exit 1
fi
echo "TESTS_DONE"
