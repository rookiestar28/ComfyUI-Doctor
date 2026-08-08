from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest


PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFTEST_PATH = PROJECT_ROOT / "tests" / "conftest.py"
VALIDATOR_PATH = PROJECT_ROOT / "scripts" / "validate_host_load.py"
BACKUP_NAME = "__init__.py" + ".bak"


def _load_validator():
    spec = importlib.util.spec_from_file_location("doctor_t31_host_validator", VALIDATOR_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_conftest():
    spec = importlib.util.spec_from_file_location("doctor_t31_conftest", CONFTEST_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_pytest_configure_never_mutates_canonical_entrypoint(tmp_path, monkeypatch):
    entrypoint = tmp_path / "__init__.py"
    original = b"# synthetic package entrypoint\n"
    entrypoint.write_bytes(original)
    conftest = _load_conftest()
    conftest.project_root = tmp_path
    rename_calls: list[tuple[Path, Path]] = []
    original_rename = Path.rename

    def tracking_rename(path: Path, target: os.PathLike[str] | str):
        rename_calls.append((Path(path), Path(target)))
        return original_rename(path, target)

    monkeypatch.setattr(Path, "rename", tracking_rename)
    config = SimpleNamespace()
    configure = getattr(conftest, "pytest_configure", None)
    unconfigure = getattr(conftest, "pytest_unconfigure", None)

    if configure is not None:
        configure(config)
    canonical_during_session = entrypoint.exists()
    backup_during_session = (tmp_path / BACKUP_NAME).exists()
    if unconfigure is not None:
        unconfigure(config)

    assert rename_calls == []
    assert canonical_during_session
    assert not backup_during_session
    assert entrypoint.read_bytes() == original


def test_no_package_entrypoint_backup_contract_remains():
    targets = [
        PROJECT_ROOT / "tests" / "conftest.py",
        PROJECT_ROOT / "scripts" / "validate_host_load.py",
        PROJECT_ROOT / "tests" / "test_a5_llm_provider_adapters.py",
        PROJECT_ROOT / "tests" / "test_r26_prestartup_encoding.py",
        PROJECT_ROOT / "tests" / "test_s10_admin_guards.py",
        PROJECT_ROOT / "__init__.py",
    ]

    for path in targets:
        source = path.read_text(encoding="utf-8")
        assert BACKUP_NAME not in source, path.relative_to(PROJECT_ROOT)

    conftest_source = (PROJECT_ROOT / "tests" / "conftest.py").read_text(encoding="utf-8")
    assert "pytest_configure" not in conftest_source
    assert "pytest_unconfigure" not in conftest_source


def test_host_validator_rejects_missing_canonical_entrypoint(tmp_path):
    validator = _load_validator()
    (tmp_path / BACKUP_NAME).write_text("# obsolete backup\n", encoding="utf-8")

    with pytest.raises(FileNotFoundError, match="canonical package entrypoint"):
        validator._project_init_path(tmp_path)


def test_canonical_entrypoint_survives_concurrent_collection():
    entrypoint = PROJECT_ROOT / "__init__.py"
    original = entrypoint.read_bytes()
    command = [
        sys.executable,
        "-m",
        "pytest",
        "--collect-only",
        "-q",
        "tests/test_t17_host_load_validator.py",
        "-p",
        "no:cacheprovider",
    ]
    processes = [
        subprocess.Popen(
            command,
            cwd=PROJECT_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        for _ in range(2)
    ]

    deadline = time.monotonic() + 30
    while any(process.poll() is None for process in processes):
        assert entrypoint.exists()
        assert entrypoint.read_bytes() == original
        if time.monotonic() >= deadline:
            for process in processes:
                process.kill()
            pytest.fail("concurrent collection subprocess timed out")
        time.sleep(0.02)

    outputs = [process.communicate(timeout=5)[0] for process in processes]
    assert [process.returncode for process in processes] == [0, 0], outputs
    assert entrypoint.read_bytes() == original
    assert not (PROJECT_ROOT / BACKUP_NAME).exists()


def test_interrupted_configure_simulation_cannot_leave_backup_state(tmp_path):
    entrypoint = tmp_path / "__init__.py"
    ready = tmp_path / "ready"
    original = b"# interruption fixture\n"
    entrypoint.write_bytes(original)
    child_code = "\n".join(
        [
            "import importlib.util, sys, time",
            "from pathlib import Path",
            "from types import SimpleNamespace",
            "spec = importlib.util.spec_from_file_location('doctor_t31_child_conftest', sys.argv[1])",
            "module = importlib.util.module_from_spec(spec)",
            "spec.loader.exec_module(module)",
            "module.project_root = Path(sys.argv[2])",
            "hook = getattr(module, 'pytest_configure', None)",
            "hook(SimpleNamespace()) if hook is not None else None",
            "Path(sys.argv[3]).write_text('ready', encoding='utf-8')",
            "time.sleep(60)",
        ]
    )
    process = subprocess.Popen(
        [sys.executable, "-c", child_code, str(CONFTEST_PATH), str(tmp_path), str(ready)],
        cwd=PROJECT_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    deadline = time.monotonic() + 10
    while not ready.exists() and process.poll() is None and time.monotonic() < deadline:
        time.sleep(0.02)
    assert ready.exists(), process.communicate(timeout=5)[0]
    process.terminate()
    process.communicate(timeout=10)

    assert entrypoint.exists()
    assert entrypoint.read_bytes() == original
    assert not (tmp_path / BACKUP_NAME).exists()


def test_e2e_sop_uses_lane_success_instead_of_fixed_pass_count():
    source = (PROJECT_ROOT / "tests" / "E2E_TESTING_SOP.md").read_text(encoding="utf-8")

    assert "Expected result: `107 passed`" not in source
    assert "successful exit status" in source
    assert "integration and stress telemetry suites excluded" in source
