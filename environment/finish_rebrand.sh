#!/usr/bin/env bash
set -euo pipefail
cd /home/ccc/projects/uav-logistics-comms
# scrub historical logs too
find environment -type f \( -name '*.log' -o -name '*.txt' -o -name '*.sh' -o -name '*.md' \) -print0 |
  xargs -0 sed -i 's/uav-logistics-comms/uav-logistics-comms/g'
if git grep -n -E '华为|赛题|数学建模|huawei|Huawei|Huawei Cup|D题|huawei-cup' -- ':!data' ':!external' ; then
  echo STILL_FOUND
  exit 1
fi
echo CLEAN
git add -A -- ':!data' ':!external'
git status --short
