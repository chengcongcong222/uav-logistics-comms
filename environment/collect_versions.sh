#!/usr/bin/env bash
set -euo pipefail
P=/home/ccc/projects/huawei-cup-d
echo "HOST_WINDOWS=Windows 10 Pro (build 26200)"
echo "WSL_VERSION=2"
echo "UBUNTU=$(lsb_release -ds)"
echo "LINUX_KERNEL=$(uname -r)"
echo "GCC=$(gcc -dumpfullversion)"
echo "GXX=$(g++ -dumpfullversion)"
echo "PYTHON=$(python3 --version | awk '{print $2}')"
echo "CMAKE=$(cmake --version | head -1 | awk '{print $3}')"
echo "NINJA=$(ninja --version)"
echo "GIT=$(git --version | awk '{print $3}')"
echo "NS3=$(cat "$P/external/ns-3.47/VERSION")"
echo "NS3_TAG=ns-3.47"
echo "NS3_TARBALL_SHA256=$(cut -d' ' -f1 "$P/external/download/ns-3.47.tar.bz2.sha256")"
echo "PROJECT_ROOT=$P"
echo "NS3_ROOT=$P/external/ns-3.47"
echo "==== RAW FILES ===="
find "$P/data/raw" -type f | sort
echo "==== ARTIFACTS ===="
ls -la "$P/results/e0" "$P/results/ns3" "$P/export"
echo "==== SMOKE SUMMARY ===="
cat "$P/results/ns3/e0_smoke_summary.csv"
echo "==== VENV PACKAGES ===="
"$P/.venv/bin/python" -m pip freeze
