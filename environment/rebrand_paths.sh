#!/usr/bin/env bash
set -euo pipefail
OLD_ROOT=/home/ccc/projects/uav-logistics-comms
NEW_ROOT=/home/ccc/projects/uav-logistics-comms
OLD_NAME=uav-logistics-comms
NEW_NAME=uav-logistics-comms

# replace paths/names in project text files (skip data/raw and external bulk)
cd "$OLD_ROOT"
# files tracked or project-owned text
find . -type f \
  \( -name '*.md' -o -name '*.txt' -o -name '*.sh' -o -name '*.py' -o -name '*.cc' -o -name '*.csv' -o -name '.gitignore' \) \
  ! -path './data/raw/*' \
  ! -path './external/ns-3.47/*' \
  ! -path './external/download/*' \
  ! -path './.venv/*' \
  ! -path './.git/*' \
  -print0 | while IFS= read -r -d '' f; do
  if grep -q "$OLD_NAME" "$f" 2>/dev/null; then
    sed -i "s/${OLD_NAME}/${NEW_NAME}/g" "$f"
    echo "updated $f"
  fi
done

echo "path rewrite done"
