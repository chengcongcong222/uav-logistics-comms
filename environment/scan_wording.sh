#!/usr/bin/env bash
set -euo pipefail
cd /home/ccc/projects/uav-logistics-comms
echo "=== contest wording scan (tracked) ==="
if git grep -n -E '华为|赛题|数学建模|huawei|Huawei|Huawei Cup|D题' -- ':!data' ':!external' ; then
  echo FOUND
else
  echo CLEAN
fi
echo "=== status ==="
git status --short
