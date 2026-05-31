import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
STALE_LABELS = [
    "Phase 2",
    "Phase2",
    "phase-2",
    "phase2-release-gate",
]


def _read(rel_path: str) -> str:
    return (ROOT / rel_path).read_text(encoding="utf-8")


def _run_help(script: str) -> str:
    result = subprocess.run(
        [sys.executable, script, "--help"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
    )
    assert result.returncode == 0
    return result.stdout + result.stderr


def _assert_no_stale_labels(text: str, label: str) -> None:
    for stale in STALE_LABELS:
        assert stale not in text, f"{label} still contains stale label: {stale}"


def test_t20_focused_gate_help_uses_neutral_naming():
    output = _run_help("scripts/focused_gate.py")

    assert "Focused Security / Contract / E2E Regression Gate" in output
    assert "tests/TEST_SOP.md" in output
    _assert_no_stale_labels(output, "focused_gate.py --help")


def test_t20_compatibility_wrapper_help_points_to_focused_gate():
    output = _run_help("scripts/phase2_gate.py")

    assert "DEPRECATED" in output
    assert "scripts/focused_gate.py" in output
    assert "Focused Security / Contract / E2E Regression Gate" in output
    _assert_no_stale_labels(output, "phase2_gate.py --help")


def test_t20_public_docs_and_workflow_use_focused_gate_labels():
    files = [
        ".github/workflows/focused-regression-gate.yml",
        "scripts/README.md",
        "tests/E2E_TESTING_SOP.md",
        "tests/e2e/README.md",
    ]

    assert (ROOT / ".github" / "workflows" / "focused-regression-gate.yml").exists()
    assert not (ROOT / ".github" / "workflows" / "phase2-release-gate.yml").exists()

    for rel_path in files:
        _assert_no_stale_labels(_read(rel_path), rel_path)


def test_t20_old_shell_wrapper_delegates_to_focused_gate():
    wrapper = _read("scripts/phase2_gate.sh")
    focused = _read("scripts/focused_gate.sh")

    assert "scripts/focused_gate.sh" in wrapper
    assert "exec \"$SCRIPT_DIR/focused_gate.sh\" \"$@\"" in wrapper
    assert "Focused Security / Contract / E2E Regression Gate" in focused
    _assert_no_stale_labels(wrapper, "phase2_gate.sh")
    _assert_no_stale_labels(focused, "focused_gate.sh")
