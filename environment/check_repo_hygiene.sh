#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

MANIFEST="environment/raw_manifest_sha256.txt"
FAIL=0

echo "==== A. tracked forbidden files ===="
tracked_bad="$(git ls-files | grep -E '^(data/raw/|external/ns-3\.47/|external/download/)' || true)"
if [[ -n "$tracked_bad" ]]; then
  echo "forbidden tracked files:"
  echo "$tracked_bad"
  echo "REPO_HYGIENE_FAILED"
  FAIL=1
else
  echo "no forbidden tracked files"
fi

echo "==== B. staged forbidden files ===="
staged_bad="$(git diff --cached --name-only | grep -E '^(data/raw/|external/ns-3\.47/|external/download/)' || true)"
if [[ -n "$staged_bad" ]]; then
  echo "forbidden staged files:"
  echo "$staged_bad"
  echo "REPO_HYGIENE_FAILED"
  FAIL=1
else
  echo "no forbidden staged files"
fi

echo "==== C. raw data SHA256 manifest ===="
if [[ -d data/raw ]]; then
  tmp="$(mktemp)"
  {
    echo "# path	size_bytes	sha256"
    find data/raw -type f -print0 | sort -z | while IFS= read -r -d '' f; do
      rel="${f#./}"
      size=$(stat -c '%s' "$f")
      sha=$(sha256sum "$f" | awk '{print $1}')
      printf '%s\t%s\t%s\n' "$rel" "$size" "$sha"
    done
  } >"$tmp"

  if [[ ! -f "$MANIFEST" ]]; then
    mv "$tmp" "$MANIFEST"
    echo "created $MANIFEST"
    echo "RAW_DATA_UNCHANGED"
  else
    # compare ignoring header
    if diff -q <(grep -v '^#' "$MANIFEST") <(grep -v '^#' "$tmp") >/dev/null; then
      rm -f "$tmp"
      echo "RAW_DATA_UNCHANGED"
    else
      echo "RAW_DATA_MODIFIED"
      diff -u <(grep -v '^#' "$MANIFEST") <(grep -v '^#' "$tmp") || true
      rm -f "$tmp"
      FAIL=1
    fi
  fi
else
  echo "data/raw missing; skip raw manifest"
  echo "RAW_DATA_UNCHANGED"
fi

if [[ "$FAIL" -ne 0 ]]; then
  echo "REPO_HYGIENE_FAILED"
  exit 1
fi

echo "REPO_HYGIENE_OK"
echo "RAW_DATA_UNCHANGED"
exit 0
