#!/usr/bin/env bash
set -euo pipefail
PROJECT_ROOT="/home/ccc/projects/huawei-cup-d"
NS3_DIR="$PROJECT_ROOT/external/ns-3.47"
ENV_DIR="$PROJECT_ROOT/environment"
cd "$NS3_DIR"

echo "==== ns-3 configure ===="
./ns3 configure --enable-examples --enable-tests 2>&1 | tee "$ENV_DIR/ns3_configure.log"

echo "==== check required modules in configure output ===="
for mod in core network internet mobility wifi applications flow-monitor; do
  if grep -qi "$mod" "$ENV_DIR/ns3_configure.log"; then
    echo "module mentioned: $mod"
  else
    echo "WARNING: module not found in configure log: $mod"
  fi
done

echo "==== ns-3 build ===="
./ns3 build 2>&1 | tee "$ENV_DIR/ns3_build.log"

echo "==== ns-3 version check ===="
./ns3 show version 2>/dev/null || true
./ns3 --version 2>/dev/null || true
cat VERSION
echo "BUILD_DONE"
