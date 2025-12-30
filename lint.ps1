# PowerShell script for linting and type checking
# Usage: .\lint.ps1 [--fix]

param(
    [switch]$Fix
)

Write-Host "🔍 Running code quality checks..." -ForegroundColor Cyan

# Check if ruff is installed
if (-not (Get-Command ruff -ErrorAction SilentlyContinue)) {
    Write-Host "❌ ruff not found. Install with: pip install -r requirements-dev.txt" -ForegroundColor Red
    exit 1
}

# Check if mypy is installed
if (-not (Get-Command mypy -ErrorAction SilentlyContinue)) {
    Write-Host "❌ mypy not found. Install with: pip install -r requirements-dev.txt" -ForegroundColor Red
    exit 1
}

Write-Host "`n📋 Step 1: Ruff Linter" -ForegroundColor Yellow
if ($Fix) {
    Write-Host "  → Running ruff check with auto-fix..." -ForegroundColor Gray
    ruff check --fix .
    Write-Host "  → Running ruff format..." -ForegroundColor Gray
    ruff format .
} else {
    Write-Host "  → Running ruff check..." -ForegroundColor Gray
    ruff check .
    Write-Host "  → Checking ruff format..." -ForegroundColor Gray
    ruff format --check .
}

if ($LASTEXITCODE -ne 0) {
    Write-Host "⚠️  Ruff found issues. Run '.\lint.ps1 -Fix' to auto-fix." -ForegroundColor Yellow
}

Write-Host "`n🔎 Step 2: MyPy Type Checker" -ForegroundColor Yellow
Write-Host "  → Running mypy..." -ForegroundColor Gray
mypy .

if ($LASTEXITCODE -ne 0) {
    Write-Host "⚠️  MyPy found type issues." -ForegroundColor Yellow
    exit 1
}

Write-Host "`n✅ All checks passed!" -ForegroundColor Green
