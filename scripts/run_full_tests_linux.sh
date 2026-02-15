#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

skip_bootstrap=0
skip_e2e=0

for arg in "$@"; do
  case "$arg" in
    --skip-bootstrap) skip_bootstrap=1 ;;
    --skip-e2e) skip_e2e=1 ;;
    *)
      echo "[full-tests] Unknown argument: $arg" >&2
      echo "Usage: bash scripts/run_full_tests_linux.sh [--skip-bootstrap] [--skip-e2e]" >&2
      exit 2
      ;;
  esac
done

log() {
  echo "[full-tests] $*"
}

fail() {
  echo "[full-tests] ERROR: $*" >&2
  exit 1
}

run_step() {
  local name="$1"
  shift
  log "$name"
  "$@"
}

# IMPORTANT: split venv by environment to avoid cross-OS contamination.
# - Windows: .venv (handled by scripts/run_full_tests_windows.ps1)
# - WSL: .venv-wsl
# - Native Linux: .venv
is_wsl=0
if [[ -n "${WSL_DISTRO_NAME:-}" ]]; then
  is_wsl=1
elif [[ -r /proc/version ]] && grep -qi microsoft /proc/version; then
  is_wsl=1
fi

if [[ "$is_wsl" -eq 1 ]]; then
  venv_dir="$repo_root/.venv-wsl"
else
  venv_dir="$repo_root/.venv"
fi

log "Using virtual environment: $venv_dir"
venv_python="$venv_dir/bin/python"

if [[ ! -x "$venv_python" ]]; then
  log "Creating project-local .venv"
  if command -v python3 >/dev/null 2>&1; then
    python3 -m venv "$venv_dir"
  elif command -v python >/dev/null 2>&1; then
    python -m venv "$venv_dir"
  else
    fail "Cannot create .venv because neither python3 nor python is available."
  fi
fi

[[ -x "$venv_python" ]] || fail "Missing interpreter at $venv_python after venv creation."

# CRITICAL: Always run test tooling via project-local .venv interpreter.
source "$venv_dir/bin/activate"

run_step "Verify .venv interpreter" "$venv_python" -c "import sys; print(sys.executable)"

if [[ "$skip_bootstrap" -eq 0 ]]; then
  run_step "Upgrade pip/setuptools/wheel in .venv" \
    "$venv_python" -m pip install --upgrade pip setuptools wheel

  if [[ -f requirements-dev.txt ]]; then
    run_step "Install Python dev dependencies" \
      "$venv_python" -m pip install -r requirements-dev.txt
  fi

  run_step "Install mandatory test tooling in .venv" \
    "$venv_python" -m pip install pre-commit detect-secrets numpy pillow aiohttp anyio
fi

[[ -f .pre-commit-config.yaml ]] || fail "Missing .pre-commit-config.yaml; cannot run required pre-commit gates."

export PRE_COMMIT_HOME="$repo_root/.tmp/pre-commit"
mkdir -p "$PRE_COMMIT_HOME"

run_step "detect-secrets gate" \
  "$venv_python" -m pre_commit run detect-secrets --all-files

run_step "pre-commit all hooks gate" \
  "$venv_python" -m pre_commit run --all-files --show-diff-on-failure

export DOCTOR_STATE_DIR="$repo_root/doctor_state/_local_unit"
mkdir -p "$DOCTOR_STATE_DIR"

if [[ -f scripts/run_unittests.py ]]; then
  run_step "Backend unit tests (scripts/run_unittests.py)" \
    "$venv_python" scripts/run_unittests.py --start-dir tests --pattern "test_*.py"
else
  run_step "Backend unit tests (pytest fallback)" \
    "$venv_python" -m pytest tests -q
fi

if [[ "$skip_e2e" -eq 0 ]]; then
  command -v node >/dev/null 2>&1 || fail "Node.js is required for E2E but was not found on PATH."
  node_version="$(node -v)"
  node_major="$(echo "$node_version" | sed -E 's/^v([0-9]+).*/\1/')"
  [[ "$node_major" =~ ^[0-9]+$ ]] || fail "Could not parse Node.js version from '$node_version'."
  (( node_major >= 18 )) || fail "Node.js 18+ is required for E2E. Current: $node_version"

  run_step "npm install" npm install
  run_step "Install Playwright Chromium" npx playwright install chromium
  run_step "Frontend E2E (npm test)" npm test
fi

log "All stages completed successfully."
