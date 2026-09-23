# E0.1 Repository Hardening Report

## Decision

**E0_1_REPOSITORY_READY**

## Git ignore protection

`.gitignore` now permanently excludes:

- `data/raw/`
- `external/ns-3.47/`
- `external/download/`
- `*.tar.bz2`, `*.tar.gz`, `*.tgz`

Still tracked (not ignored):

- `data/processed/`, `export/`, `results/`, `environment/`, `validation/`, `docs/model/`, `src/`

## Tracked forbidden files

**NONE** — `git ls-files` shows no paths under `data/raw/`, `external/ns-3.47/`, or `external/download/`.

## Staged forbidden files

**NONE** — `git diff --cached --name-only` is clean of forbidden paths.

## Raw data SHA256 manifest

Created: `environment/raw_manifest_sha256.txt`

- 19 raw files inventoried
- Columns: relative path, size_bytes, sha256
- Manifest itself is tracked (hashes only, no raw payloads)
- Re-check result: **RAW_DATA_UNCHANGED**

## E0 regression

- `bash environment/check_repo_hygiene.sh` → `REPO_HYGIENE_OK` / `RAW_DATA_UNCHANGED`
- `bash environment/check_final.sh` → hygiene first, then E0 logs
- ns-3 tests remain **800/800 PASS**
- E0 smoke remains `tx=23, rx=1, pdr=0.0434783` (intentionally untouched)
- PDR not tuned in this gate

## Commit

Message: `E0.1: harden repository boundaries`

## Push

Remote: `chengcongcong222/uav-logistics-comms` (private)  
Status: pushed to `origin/main`

## Next Gate

**E1_DATA_INGESTION**
