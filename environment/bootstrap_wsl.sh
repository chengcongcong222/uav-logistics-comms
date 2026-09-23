#!/usr/bin/env bash
# Idempotent bootstrap for uav-logistics-comms (E0 environment only).
# Does NOT modify Windows system settings and does NOT delete existing Linux envs.
set -euo pipefail

log() { printf '[bootstrap] %s\n' "$*"; }
die() { printf '[bootstrap][ERROR] %s\n' "$*" >&2; exit 1; }

if ! grep -qi microsoft /proc/version 2>/dev/null && ! grep -qi wsl /proc/version 2>/dev/null; then
  log "WARNING: this does not look like WSL; continue anyway (Linux is OK)."
fi

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"
log "PROJECT_ROOT=$PROJECT_ROOT"

if [[ -f /etc/os-release ]]; then
  # shellcheck disable=SC1091
  . /etc/os-release
  log "OS=${PRETTY_NAME:-unknown}"
fi

export DEBIAN_FRONTEND=noninteractive

need_apt=0
for pkg in build-essential g++ python3 python3-pip python3-venv cmake ninja-build git ccache pkg-config unzip p7zip-full; do
  if ! dpkg -s "$pkg" >/dev/null 2>&1; then
    need_apt=1
    break
  fi
done

if [[ "$need_apt" -eq 1 ]]; then
  log "Installing missing apt packages (requires sudo)..."
  sudo apt-get update -y
  sudo apt-get install -y \
    build-essential \
    g++ \
    python3 \
    python3-pip \
    python3-venv \
    cmake \
    ninja-build \
    git \
    ccache \
    gdb \
    valgrind \
    pkg-config \
    unzip \
    p7zip-full
else
  log "All required apt packages already present."
fi

if [[ ! -d "$PROJECT_ROOT/.venv" ]]; then
  log "Creating Python venv at $PROJECT_ROOT/.venv"
  python3 -m venv "$PROJECT_ROOT/.venv"
else
  log "Python venv already exists."
fi

# shellcheck disable=SC1091
source "$PROJECT_ROOT/.venv/bin/activate"
python -m pip install --upgrade pip setuptools wheel

if [[ -f "$PROJECT_ROOT/environment/requirements.txt" ]]; then
  python -m pip install -r "$PROJECT_ROOT/environment/requirements.txt"
else
  log "requirements.txt not found yet; installing E0 baseline packages..."
  python -m pip install numpy scipy pandas openpyxl matplotlib rasterio pyproj
fi

log "---- tool versions ----"
uname -a || true
( lsb_release -a 2>/dev/null || true )
gcc --version | head -1
g++ --version | head -1
python3 --version
python --version
cmake --version | head -1
ninja --version
git --version
ccache --version | head -1 || true

log "Bootstrap complete (idempotent)."
log "Next: ensure ns-3.47 under external/ns-3.47, then run configure/build/test."
log "If Windows host features / reboot / admin rights are required, perform them manually; this script will not change Windows settings."
