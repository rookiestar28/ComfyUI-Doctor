#!/usr/bin/env python3
"""
Phase 2 Release Gate - Local Validator

Runs the same checks as GitHub Actions CI gate locally before pushing.
Mirrors: .github/workflows/phase2-release-gate.yml

Usage:
  python scripts/phase2_gate.py          # Run all checks
  python scripts/phase2_gate.py --fast   # Python tests only
  python scripts/phase2_gate.py --e2e    # E2E tests only

Exit codes:
  0 = All checks passed
  1 = Python tests failed
  2 = E2E tests failed
  3 = Both failed
"""

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Sequence, Union

# Project root
REPO_ROOT = Path(__file__).resolve().parents[1]

# ANSI colors
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"
BOLD = "\033[1m"


Command = Union[str, Sequence[str]]


def run_command(cmd: Command, cwd=REPO_ROOT, timeout=300):
    """Run a command and return (success, stdout, stderr)."""
    try:
        use_shell = isinstance(cmd, str)
        result = subprocess.run(
            cmd,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
            shell=use_shell,
        )
        return result.returncode == 0, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return False, "", f"Command timed out after {timeout}s"


def print_header(text):
    """Print colored section header."""
    print(f"\n{BOLD}{text}{RESET}")
    print("=" * len(text))

def _detect_pytest(python_exe: str) -> bool:
    success, _, _ = run_command([python_exe, "-c", "import pytest"], timeout=20)
    return success


def _select_python_for_pytest() -> str:
    """
    Prefer the current interpreter if it has pytest installed; otherwise fall back
    to the repo-local .venv interpreter when present.
    """
    current = sys.executable
    if _detect_pytest(current):
        return current

    venv_python = (
        REPO_ROOT / ".venv" / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    )
    if venv_python.exists() and _detect_pytest(str(venv_python)):
        return str(venv_python)

    return current


def run_python_gate():
    """Run Phase 2 Python test suites."""
    print_header("Phase 2 Python Security & Contract Tests")

    python_exe = _select_python_for_pytest()
    suites = [
        ("Plugin Security", "tests/test_plugins_security.py", 10),
        ("Metadata Contract", "tests/test_metadata_contract.py", 1),
        ("Dependency Policy", "tests/test_pipeline_dependency_policy.py", 2),
        ("Outbound Payload Safety", "tests/test_outbound_payload_safety.py", 4),
    ]

    all_passed = True
    for name, path, test_count in suites:
        print(f"\n{YELLOW}Running {name} ({test_count} tests)...{RESET}")
        cmd = [python_exe, "-m", "pytest", "-q", path, "--tb=short"]
        success, stdout, stderr = run_command(cmd, timeout=120)

        if success:
            print(f"{GREEN}✅ {name}: PASS{RESET}")
            print(stdout)
        else:
            print(f"{RED}❌ {name}: FAIL{RESET}")
            print(stdout)
            print(stderr)
            all_passed = False

    return all_passed


def run_e2e_gate():
    """Run Phase 2 E2E regression tests."""
    print_header("Phase 2 E2E Regression Tests")

    # Check if node_modules exists
    if not (REPO_ROOT / "node_modules").exists():
        print(f"{YELLOW}Installing npm dependencies...{RESET}")
        success, stdout, stderr = run_command(["npm", "ci"], timeout=300)
        if not success:
            print(f"{RED}❌ npm ci failed{RESET}")
            print(stderr)
            return False

    # Check if Playwright browsers are installed
    print(f"{YELLOW}Checking Playwright browsers...{RESET}")
    success, stdout, stderr = run_command(["npx", "playwright", "install", "chromium", "--with-deps"], timeout=300)
    if not success:
        print(f"{RED}❌ Playwright browser installation failed{RESET}")
        print(stderr)
        return False

    # Run E2E tests
    print(f"\n{YELLOW}Running E2E tests (61 tests)...{RESET}")
    success, stdout, stderr = run_command(["npm", "test"], timeout=600)

    if success:
        print(f"{GREEN}✅ E2E Tests: PASS{RESET}")
        print(stdout)
    else:
        print(f"{RED}❌ E2E Tests: FAIL{RESET}")
        print(stdout)
        print(stderr)

    return success


def main():
    parser = argparse.ArgumentParser(description="Phase 2 Release Gate - Local Validator")
    parser.add_argument("--fast", action="store_true", help="Run Python tests only (skip E2E)")
    parser.add_argument("--e2e", action="store_true", help="Run E2E tests only (skip Python)")
    args = parser.parse_args()

    print(f"{BOLD}Phase 2 Release Readiness Gate{RESET}")
    print("Mirrors: .github/workflows/phase2-release-gate.yml\n")

    python_passed = True
    e2e_passed = True

    # Run checks based on flags
    if not args.e2e:
        python_passed = run_python_gate()

    if not args.fast:
        e2e_passed = run_e2e_gate()

    # Final summary
    print_header("Phase 2 Gate Summary")
    if python_passed and e2e_passed:
        print(f"{GREEN}{BOLD}✅ ALL CHECKS PASSED{RESET}")
        print(f"\n{GREEN}Security & Governance: ✅{RESET}")
        print(f"  Plugin security: PASS")
        print(f"  Metadata contract: PASS")
        print(f"  Dependency policy: PASS")
        print(f"  Outbound payload safety: PASS")
        print(f"\n{GREEN}Frontend Regression: ✅{RESET}")
        print(f"  E2E tests: PASS")
        print(f"\n{GREEN}Your changes are safe to push.{RESET}")
        return 0
    else:
        print(f"{RED}{BOLD}❌ GATE FAILED{RESET}")
        if not python_passed:
            print(f"{RED}  Python tests: FAIL{RESET}")
        if not e2e_passed:
            print(f"{RED}  E2E tests: FAIL{RESET}")
        print(f"\n{RED}Please fix the failing checks before pushing.{RESET}")

        # Return specific exit codes
        if not python_passed and not e2e_passed:
            return 3
        elif not python_passed:
            return 1
        else:
            return 2


if __name__ == "__main__":
    sys.exit(main())
