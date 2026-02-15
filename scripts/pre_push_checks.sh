#!/usr/bin/env bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$repo_root"

log() {
  echo "[pre-push] $*"
}

fail() {
  echo "[pre-push] ERROR: $*" >&2
  exit 1
}

run_windows_full_tests() {
  local ps_script="$repo_root/scripts/run_full_tests_windows.ps1"
  [[ -f "$ps_script" ]] || fail "Missing script: $ps_script"
  local ps_script_for_windows="$ps_script"

  # WSL path compatibility: convert /mnt/... to Windows path for powershell.exe.
  if [[ "$ps_script_for_windows" == /mnt/* ]] && command -v wslpath >/dev/null 2>&1; then
    ps_script_for_windows="$(wslpath -w "$ps_script_for_windows")"
  fi

  if command -v powershell.exe >/dev/null 2>&1; then
    powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "\$ErrorActionPreference='Stop'; & '$ps_script_for_windows'; if (\$LASTEXITCODE -and \$LASTEXITCODE -ne 0) { exit \$LASTEXITCODE }"
    return
  fi
  if command -v pwsh >/dev/null 2>&1; then
    pwsh -NoProfile -Command "\$ErrorActionPreference='Stop'; & '$ps_script'; if (\$LASTEXITCODE -and \$LASTEXITCODE -ne 0) { exit \$LASTEXITCODE }"
    return
  fi
  if command -v powershell >/dev/null 2>&1; then
    powershell -NoProfile -ExecutionPolicy Bypass -Command "\$ErrorActionPreference='Stop'; & '$ps_script'; if (\$LASTEXITCODE -and \$LASTEXITCODE -ne 0) { exit \$LASTEXITCODE }"
    return
  fi

  fail "Windows environment detected, but no PowerShell runtime found."
}

run_linux_full_tests() {
  local sh_script="$repo_root/scripts/run_full_tests_linux.sh"
  [[ -f "$sh_script" ]] || fail "Missing script: $sh_script"
  bash "$sh_script"
}

is_windows_shell=0
if [[ "${OS:-}" == "Windows_NT" ]]; then
  is_windows_shell=1
elif [[ "$(uname -s 2>/dev/null || echo unknown)" =~ ^(MINGW|MSYS|CYGWIN) ]]; then
  is_windows_shell=1
fi

log "Running mandatory full test gate before push"
if [[ "$is_windows_shell" -eq 1 ]]; then
  run_windows_full_tests
else
  run_linux_full_tests
fi

log "Full test gate passed; push is allowed."
