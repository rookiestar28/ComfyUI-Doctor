#!/usr/bin/env python3
"""
Focused Security / Contract / E2E Regression Gate - Local Validator

Runs the supplemental focused gate locally before pushing. This lane is useful
for plugin security, metadata, dependency-policy, outbound-payload, and E2E
regression checks, but it is not a replacement for tests/TEST_SOP.md.
Mirrors: .github/workflows/focused-regression-gate.yml

Usage:
  python scripts/focused_gate.py          # Run all focused checks
  python scripts/focused_gate.py --fast   # Python tests only
  python scripts/focused_gate.py --e2e    # E2E tests only

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


REPO_ROOT = Path(__file__).resolve().parents[1]

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
    """Run focused Python security and contract test suites."""
    print_header("Focused Python Security & Contract Tests")

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
            print(f"{GREEN}PASS {name}: PASS{RESET}")
            print(stdout)
        else:
            print(f"{RED}FAIL {name}: FAIL{RESET}")
            print(stdout)
            print(stderr)
            all_passed = False

    return all_passed


def run_e2e_gate():
    """Run focused E2E regression tests."""
    print_header("Focused E2E Regression Tests")

    if not (REPO_ROOT / "node_modules").exists():
        print(f"{YELLOW}Installing npm dependencies...{RESET}")
        success, stdout, stderr = run_command(["npm", "ci"], timeout=300)
        if not success:
            print(f"{RED}FAIL npm ci failed{RESET}")
            print(stderr)
            return False

    print(f"{YELLOW}Checking Playwright browsers...{RESET}")
    success, stdout, stderr = run_command(
        ["npx", "playwright", "install", "chromium", "--with-deps"],
        timeout=300,
    )
    if not success:
        print(f"{RED}FAIL Playwright browser installation failed{RESET}")
        print(stderr)
        return False

    print(f"\n{YELLOW}Running E2E tests...{RESET}")
    success, stdout, stderr = run_command(["npm", "test"], timeout=600)

    if success:
        print(f"{GREEN}PASS E2E Tests: PASS{RESET}")
        print(stdout)
    else:
        print(f"{RED}FAIL E2E Tests: FAIL{RESET}")
        print(stdout)
        print(stderr)

    return success


def main():
    parser = argparse.ArgumentParser(
        description="Focused Security / Contract / E2E Regression Gate - Local Validator",
        epilog="Supplemental lane only; final acceptance still requires tests/TEST_SOP.md.",
    )
    parser.add_argument("--fast", action="store_true", help="Run Python tests only (skip E2E)")
    parser.add_argument("--e2e", action="store_true", help="Run E2E tests only (skip Python)")
    args = parser.parse_args()

    print(f"{BOLD}Focused Security / Contract / E2E Regression Gate{RESET}")
    print("Mirrors: .github/workflows/focused-regression-gate.yml")
    print("Note: this supplemental lane does not replace tests/TEST_SOP.md.\n")

    python_passed = True
    e2e_passed = True

    if not args.e2e:
        python_passed = run_python_gate()

    if not args.fast:
        e2e_passed = run_e2e_gate()

    print_header("Focused Gate Summary")
    if python_passed and e2e_passed:
        print(f"{GREEN}{BOLD}PASS ALL FOCUSED CHECKS PASSED{RESET}")
        print(f"\n{GREEN}Security & Governance: PASS{RESET}")
        print("  Plugin security: PASS")
        print("  Metadata contract: PASS")
        print("  Dependency policy: PASS")
        print("  Outbound payload safety: PASS")
        print(f"\n{GREEN}Frontend Regression: PASS{RESET}")
        print("  E2E tests: PASS")
        print(f"\n{GREEN}Focused gate is green; run the full TEST_SOP gate before acceptance.{RESET}")
        return 0

    print(f"{RED}{BOLD}FAIL FOCUSED GATE FAILED{RESET}")
    if not python_passed:
        print(f"{RED}  Python tests: FAIL{RESET}")
    if not e2e_passed:
        print(f"{RED}  E2E tests: FAIL{RESET}")
    print(f"\n{RED}Please fix the failing checks before pushing.{RESET}")

    if not python_passed and not e2e_passed:
        return 3
    if not python_passed:
        return 1
    return 2


if __name__ == "__main__":
    sys.exit(main())
