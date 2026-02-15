param(
    [switch]$SkipBootstrap,
    [switch]$SkipE2E
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

function Write-Step([string]$Message) {
    Write-Host "[full-tests] $Message" -ForegroundColor Cyan
}

function Fail([string]$Message) {
    Write-Error "[full-tests] $Message"
    exit 1
}

function Run-Checked([string]$Name, [scriptblock]$Action) {
    Write-Step $Name
    & $Action
    if ($LASTEXITCODE -ne 0) {
        Fail "$Name failed (exit code: $LASTEXITCODE)"
    }
}

$VenvDir = Join-Path $RepoRoot ".venv"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"

if (-not (Test-Path $VenvPython)) {
    Write-Step "Creating project-local .venv"
    if (Get-Command py -ErrorAction SilentlyContinue) {
        & py -3 -m venv $VenvDir
    } elseif (Get-Command python -ErrorAction SilentlyContinue) {
        & python -m venv $VenvDir
    } else {
        Fail "Cannot create .venv because neither 'py' nor 'python' is available."
    }
}

if (-not (Test-Path $VenvPython)) {
    Fail "Missing interpreter at $VenvPython after venv creation."
}

# CRITICAL: Always run test tooling via project-local .venv interpreter.
$env:VIRTUAL_ENV = $VenvDir
$env:PATH = "$(Join-Path $VenvDir 'Scripts');$env:PATH"

Run-Checked "Verify .venv interpreter" {
    & $VenvPython -c "import sys; print(sys.executable)"
}

if (-not $SkipBootstrap) {
    Run-Checked "Upgrade pip/setuptools/wheel in .venv" {
        & $VenvPython -m pip install --upgrade pip setuptools wheel
    }

    if (Test-Path "requirements-dev.txt") {
        Run-Checked "Install Python dev dependencies" {
            & $VenvPython -m pip install -r requirements-dev.txt
        }
    }

    Run-Checked "Install mandatory test tooling in .venv" {
        & $VenvPython -m pip install pre-commit detect-secrets numpy pillow aiohttp anyio
    }
}

if (-not (Test-Path ".pre-commit-config.yaml")) {
    Fail "Missing .pre-commit-config.yaml; cannot run required pre-commit gates."
}

# IMPORTANT: use a dedicated repo-local cache path for full-test runs.
# This avoids stale lock conflicts from older interrupted runs.
$env:PRE_COMMIT_HOME = Join-Path $RepoRoot ".tmp\pre-commit-win-main"
New-Item -ItemType Directory -Force $env:PRE_COMMIT_HOME | Out-Null

Run-Checked "detect-secrets gate" {
    & $VenvPython -m pre_commit run detect-secrets --all-files
}

Run-Checked "pre-commit all hooks gate" {
    & $VenvPython -m pre_commit run --all-files --show-diff-on-failure
}

$env:DOCTOR_STATE_DIR = Join-Path $RepoRoot "doctor_state\_local_unit"
New-Item -ItemType Directory -Force $env:DOCTOR_STATE_DIR | Out-Null

if (Test-Path "scripts/run_unittests.py") {
    Run-Checked "Backend unit tests (scripts/run_unittests.py)" {
        & $VenvPython scripts/run_unittests.py --start-dir tests --pattern "test_*.py"
    }
} else {
    Run-Checked "Backend unit tests (pytest fallback)" {
        & $VenvPython -m pytest tests -q
    }
}

if (-not $SkipE2E) {
    if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
        Fail "Node.js is required for E2E but was not found on PATH."
    }

    $NodeVersion = (& node -v).Trim()
    if ($NodeVersion -notmatch "^v(\d+)") {
        Fail "Could not parse Node.js version from '$NodeVersion'."
    }

    $NodeMajor = [int]$Matches[1]
    if ($NodeMajor -lt 18) {
        Fail "Node.js 18+ is required for E2E. Current: $NodeVersion"
    }

    Run-Checked "npm install" { npm install }
    Run-Checked "Install Playwright Chromium" { npx playwright install chromium }
    Run-Checked "Frontend E2E (npm test)" { npm test }
}

Write-Host "[full-tests] All stages completed successfully." -ForegroundColor Green
