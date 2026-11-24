"""The full-gate scripts must install frontend dependencies with `npm ci`.

`npm install` rewrites package-lock.json (npm 11 drops optional `libc` fields), which left a dirty
tracked file after every acceptance run. `npm ci` installs exactly what the lockfile pins and never
writes it, and it fails when package.json and the lockfile disagree.
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
WINDOWS_SCRIPT = REPO_ROOT / "scripts" / "run_full_tests_windows.ps1"
LINUX_SCRIPT = REPO_ROOT / "scripts" / "run_full_tests_linux.sh"
TEST_SOP = REPO_ROOT / "tests" / "TEST_SOP.md"


def _command_lines(path: Path) -> list[str]:
    """Non-comment script lines, so prose that mentions npm install cannot satisfy or break the guard."""
    lines = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        stripped = raw.strip()
        if stripped and not stripped.startswith("#"):
            lines.append(stripped)
    return lines


def test_full_gate_scripts_install_with_npm_ci_only():
    for script in (WINDOWS_SCRIPT, LINUX_SCRIPT):
        commands = _command_lines(script)
        assert any(re.search(r"\bnpm ci\b", line) for line in commands), script.name
        offenders = [line for line in commands if re.search(r"\bnpm install\b", line)]
        assert offenders == [], f"{script.name}: {offenders}"


def test_npm_ci_runs_after_the_supply_chain_gate_and_before_the_browser_install():
    for script in (WINDOWS_SCRIPT, LINUX_SCRIPT):
        text = script.read_text(encoding="utf-8")
        assert (
            text.index("Supply-chain dependency gate")
            < text.index("npm ci")
            < text.index("playwright install chromium")
        ), script.name


def test_test_sop_documents_npm_ci_for_the_gate():
    text = TEST_SOP.read_text(encoding="utf-8")
    assert "Frontend deps installed: `npm ci`" in text
    assert "run `npm ci` with the same Node version" in text
    assert "Frontend deps installed: `npm install`" not in text
