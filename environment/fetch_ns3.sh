#!/usr/bin/env bash
set -euo pipefail
PROJECT_ROOT="/home/ccc/projects/uav-logistics-comms"
EXTERNAL="$PROJECT_ROOT/external"
NS3_DIR="$EXTERNAL/ns-3.47"
DOWNLOAD_DIR="$EXTERNAL/download"
mkdir -p "$EXTERNAL" "$DOWNLOAD_DIR"

# Prefer official release tarball of pure ns-3.47 (NOT ns-allinone as build system).
# Official GitLab tag archive is the release source at tag ns-3.47.
PRIMARY_URL="https://gitlab.com/nsnam/ns-3-dev/-/archive/ns-3.47/ns-3-dev-ns-3.47.tar.bz2"
# Fallback: extract ns-3.47 from official ns-allinone release if needed.
FALLBACK_URL="https://www.nsnam.org/releases/ns-allinone-3.47.tar.bz2"

if [[ -d "$NS3_DIR" && -f "$NS3_DIR/VERSION" ]]; then
  echo "ns-3 already present at $NS3_DIR"
else
  rm -rf "$NS3_DIR"
  mkdir -p "$DOWNLOAD_DIR"
  TARBALL="$DOWNLOAD_DIR/ns-3.47.tar.bz2"
  if [[ ! -f "$TARBALL" ]]; then
    echo "Downloading $PRIMARY_URL"
    curl -fL --retry 3 --retry-delay 2 -o "$TARBALL" "$PRIMARY_URL"
  fi
  echo "SHA256 of tarball:"
  sha256sum "$TARBALL" | tee "$DOWNLOAD_DIR/ns-3.47.tar.bz2.sha256"
  TMP_EXTRACT="$DOWNLOAD_DIR/extract_ns3"
  rm -rf "$TMP_EXTRACT"
  mkdir -p "$TMP_EXTRACT"
  tar -xjf "$TARBALL" -C "$TMP_EXTRACT"
  # Expected top-level dir name from gitlab archive
  SRC_DIR=$(find "$TMP_EXTRACT" -maxdepth 1 -mindepth 1 -type d | head -1)
  echo "Extracted source dir: $SRC_DIR"
  if [[ -f "$SRC_DIR/VERSION" ]] && grep -q '3.47' "$SRC_DIR/VERSION"; then
    mv "$SRC_DIR" "$NS3_DIR"
  else
    echo "Primary extract missing VERSION=3.47; trying allinone fallback extraction of ns-3.47 only"
    FALLBACK_TB="$DOWNLOAD_DIR/ns-allinone-3.47.tar.bz2"
    if [[ ! -f "$FALLBACK_TB" ]]; then
      curl -fL --retry 3 --retry-delay 2 -o "$FALLBACK_TB" "$FALLBACK_URL"
    fi
    sha256sum "$FALLBACK_TB" | tee "$DOWNLOAD_DIR/ns-allinone-3.47.tar.bz2.sha256"
    rm -rf "$TMP_EXTRACT"
    mkdir -p "$TMP_EXTRACT"
    tar -xjf "$FALLBACK_TB" -C "$TMP_EXTRACT"
    ALLINONE=$(find "$TMP_EXTRACT" -maxdepth 1 -mindepth 1 -type d | head -1)
    if [[ -d "$ALLINONE/ns-3.47" ]]; then
      mv "$ALLINONE/ns-3.47" "$NS3_DIR"
    else
      echo "Failed to locate ns-3.47 directory" >&2
      exit 1
    fi
  fi
fi

cd "$NS3_DIR"
echo "==== ns-3 version files ===="
if [[ -f VERSION ]]; then
  echo "VERSION=$(cat VERSION)"
fi
if [[ -f .git/HEAD ]] || [[ -d .git ]]; then
  git rev-parse HEAD || true
  git describe --tags --always || true
fi
# Also record VERSION.txt content if present
[[ -f VERSION ]] && cat VERSION
ls -la | head -30
echo "NS3_READY at $NS3_DIR"
