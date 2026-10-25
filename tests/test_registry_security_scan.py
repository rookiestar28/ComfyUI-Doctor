"""Fail the backend gate on the Registry's source-level publishing security rules."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RULES = "S102,S307,E702"


def _run(command):
    try:
        result = subprocess.run(command, cwd=PROJECT_ROOT, capture_output=True,
                                text=True, encoding="utf-8", errors="replace", check=False)
    except OSError as exc:
        raise RuntimeError(f"Registry scan tool unavailable: {command[0]}") from exc
    return result


def _tracked_python_files():
    result = _run(["git", "ls-files", "-z", "--", "*.py"])
    if result.returncode:
        raise RuntimeError(f"Registry scan cannot enumerate tracked Python: {result.stderr}")
    paths = [path for path in result.stdout.split("\0") if path]
    if not paths:
        raise RuntimeError("Registry scan found no tracked Python files")
    return paths


def _scan(paths):
    if not paths:
        raise RuntimeError("Registry scan requires a nonempty file inventory")
    findings = []
    # IMPORTANT: keep the isolated rules mandatory; repo excludes must not hide publishing failures.
    # Batch paths below the Windows command-line limit as the tracked inventory grows.
    remaining = [os.fspath(path) for path in paths]
    while remaining:
        batch = [remaining.pop(0)]
        size = len(batch[0]) + 3
        while remaining and size + len(remaining[0]) + 3 < 8000:
            item = remaining.pop(0)
            batch.append(item)
            size += len(item) + 3
        result = _run([sys.executable, "-m", "ruff", "check", "--isolated", "--no-cache",
                       "--select", RULES, "--output-format", "concise", "--", *batch])
        if result.returncode not in (0, 1):
            raise RuntimeError(f"Registry security scan failed to run: {result.stderr or result.stdout}")
        if result.returncode:
            findings.append(result.stdout + result.stderr)
    return "\n".join(findings)


def test_all_tracked_python_passes_registry_security_rules():
    findings = _scan(_tracked_python_files())
    assert not findings, f"Registry publishing security findings:\n{findings}"


def test_scan_reports_all_three_rules_and_file_lines_without_executing_fixture(tmp_path):
    fixture = tmp_path / "unsafe_fixture.py"
    fixture.write_text("exec('pass')\neval('1')\na = 1; b = 2\n", encoding="utf-8")
    findings = _scan([fixture])
    for line, code in ((1, "S102"), (2, "S307"), (3, "E702")):
        assert f"unsafe_fixture.py:{line}:" in findings and code in findings


def test_empty_inventory_and_missing_tool_fail_explicitly(monkeypatch):
    with pytest.raises(RuntimeError, match="nonempty"):
        _scan([])
    monkeypatch.setattr(subprocess, "run", lambda *_args, **_kwargs:
                        subprocess.CompletedProcess([], 0, "", ""))
    with pytest.raises(RuntimeError, match="no tracked Python"):
        _tracked_python_files()

    def missing(*_args, **_kwargs):
        raise FileNotFoundError("synthetic missing tool")

    monkeypatch.setattr(subprocess, "run", missing)
    with pytest.raises(RuntimeError, match="tool unavailable"):
        _scan(["synthetic.py"])


def test_ruff_invocation_error_is_not_treated_as_clean(monkeypatch):
    monkeypatch.setattr(subprocess, "run", lambda *_args, **_kwargs:
                        subprocess.CompletedProcess([], 2, "", "synthetic Ruff failure"))
    with pytest.raises(RuntimeError, match="failed to run.*synthetic Ruff failure"):
        _scan(["synthetic.py"])
