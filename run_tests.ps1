<# 
.SYNOPSIS
    Run all ComfyUI-Doctor unit tests without pytest.
    
.DESCRIPTION
    This script runs tests using Python's unittest directly, 
    bypassing pytest's package discovery which fails due to 
    relative imports in __init__.py (T6 issue).
    
.EXAMPLE
    .\run_tests.ps1
    .\run_tests.ps1 -Verbose
#>

param(
    [switch]$Verbose,
    [switch]$StopOnError
)

$ErrorActionPreference = if ($StopOnError) { "Stop" } else { "Continue" }

# Change to tests directory
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$TestsDir = Join-Path $ScriptDir "tests"

if (-not (Test-Path $TestsDir)) {
    Write-Error "Tests directory not found: $TestsDir"
    exit 1
}

Push-Location $TestsDir

# Get all test files
$TestFiles = Get-ChildItem -Filter "test_*.py" | Where-Object { $_.Name -notmatch "test_integrations|test_nodes_deep|test_smart_debug" }

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  ComfyUI-Doctor Test Runner" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

$TotalTests = 0
$PassedFiles = 0
$FailedFiles = 0

foreach ($TestFile in $TestFiles) {
    Write-Host "Running: $($TestFile.Name)" -ForegroundColor Yellow
    
    if ($Verbose) {
        $result = python $TestFile.FullName 2>&1
        Write-Host $result
    }
    else {
        $result = python $TestFile.FullName 2>&1
    }
    
    # Parse result
    if ($LASTEXITCODE -eq 0) {
        # Extract test count from output
        $match = $result | Select-String -Pattern "Ran (\d+) tests?"
        if ($match) {
            $count = [int]$match.Matches[0].Groups[1].Value
            $TotalTests += $count
        }
        Write-Host "  ✅ PASSED" -ForegroundColor Green
        $PassedFiles++
    }
    else {
        Write-Host "  ❌ FAILED" -ForegroundColor Red
        if (-not $Verbose) {
            Write-Host $result -ForegroundColor DarkGray
        }
        $FailedFiles++
    }
}

Pop-Location

# Summary
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  Summary" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Total tests run: $TotalTests"
Write-Host "  Files passed:    $PassedFiles" -ForegroundColor Green
if ($FailedFiles -gt 0) {
    Write-Host "  Files failed:    $FailedFiles" -ForegroundColor Red
    exit 1
}
else {
    Write-Host "`n  All tests passed! ✅" -ForegroundColor Green
    exit 0
}
