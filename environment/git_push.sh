#!/usr/bin/env bash
set -euo pipefail
cd /home/ccc/projects/huawei-cup-d
git config --local credential.helper ''
git config --local credential.helper '!gh auth git-credential'
git config --local user.name "chengcongcong222"
git config --local user.email "chengcongcong222@users.noreply.github.com"
echo "=== remote ==="
git remote -v
echo "=== push ==="
git push -u origin main
echo "=== status ==="
git status -sb
git log --oneline -3
