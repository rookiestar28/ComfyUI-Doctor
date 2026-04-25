#!/usr/bin/env python3
"""Run the optional CI coverage baseline lane."""

from __future__ import annotations

import argparse
import importlib.util
import os
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def build_coverage_command(
    python_exe: str,
    *,
    xml_path: str = "coverage.xml",
    fail_under: int = 0,
) -> list[str]:
    command = [
        python_exe,
        "-m",
        "pytest",
        "tests",
        "--cov=.",
        "--cov-report=term-missing:skip-covered",
        f"--cov-fail-under={fail_under}",
    ]
    if xml_path:
        command.append(f"--cov-report=xml:{xml_path}")
    return command


def _require_pytest_cov() -> None:
    missing = [
        module_name
        for module_name in ("pytest", "pytest_cov")
        if importlib.util.find_spec(module_name) is None
    ]
    if missing:
        packages = ", ".join(missing)
        raise RuntimeError(
            f"Missing coverage dependency: {packages}. "
            "Install dev dependencies with: python -m pip install -r requirements-dev.txt"
        )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run pytest with coverage baseline reporting.")
    parser.add_argument(
        "--xml",
        default="coverage.xml",
        help="Coverage XML output path. Use an empty value to skip XML output.",
    )
    parser.add_argument(
        "--fail-under",
        type=int,
        default=0,
        help="Coverage threshold. Defaults to 0 for baseline reporting only.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    try:
        _require_pytest_cov()
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    env = os.environ.copy()
    env.setdefault("DOCTOR_STATE_DIR", str(PROJECT_ROOT / "doctor_state" / "_coverage"))
    env.setdefault("MOLTBOT_STATE_DIR", str(PROJECT_ROOT / "moltbot_state" / "_coverage"))

    command = build_coverage_command(
        sys.executable,
        xml_path=args.xml,
        fail_under=args.fail_under,
    )
    return subprocess.call(command, cwd=PROJECT_ROOT, env=env)


if __name__ == "__main__":
    raise SystemExit(main())
