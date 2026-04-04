import importlib
import sys
import types
import uuid
from contextlib import contextmanager
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parent.parent
INTERNAL_TOP_LEVELS = {
    "analyzer",
    "config",
    "history_store",
    "logger",
    "outbound",
    "rate_limiter",
    "session_manager",
    "statistics",
    "system_info",
    "telemetry",
    "services",
    "pipeline",
}
PACKAGE_MODULES = [
    "config",
    "history_store",
    "logger",
    "outbound",
    "session_manager",
    "statistics",
    "system_info",
    "telemetry",
    "analyzer",
    "services.job_manager",
    "services.routes",
    "services.intent",
    "services.diagnostics.store",
    "services.diagnostics.runner",
    "services.policy",
    "services.providers.base",
    "services.providers.registry",
    "services.prompt_composer",
    "services.log_ring_buffer",
]


def _should_detach(name: str) -> bool:
    return any(name == prefix or name.startswith(f"{prefix}.") for prefix in INTERNAL_TOP_LEVELS)


@contextmanager
def _synthetic_package_import_context():
    package_name = f"doctor_pkg_r25_{uuid.uuid4().hex}"
    original_sys_path = list(sys.path)
    detached = {name: sys.modules.pop(name) for name in list(sys.modules) if _should_detach(name)}

    filtered_path = []
    for entry in original_sys_path:
        try:
            if Path(entry or ".").resolve() == PROJECT_ROOT:
                continue
        except Exception:
            pass
        filtered_path.append(entry)

    try:
        sys.path[:] = filtered_path
        package = types.ModuleType(package_name)
        package.__file__ = str(PROJECT_ROOT / "__init__.py")
        package.__package__ = package_name
        package.__path__ = [str(PROJECT_ROOT)]
        sys.modules[package_name] = package
        yield package_name
    finally:
        for name in list(sys.modules):
            if name == package_name or name.startswith(f"{package_name}."):
                sys.modules.pop(name, None)
        sys.modules.update(detached)
        sys.path[:] = original_sys_path


@pytest.mark.parametrize("module_name", PACKAGE_MODULES)
def test_package_modules_import_without_repo_root_sys_path(module_name):
    """R25: package-loaded modules must not rely on bare internal top-level imports."""
    with _synthetic_package_import_context() as package_name:
        module = importlib.import_module(f"{package_name}.{module_name}")
        assert module.__name__ == f"{package_name}.{module_name}"
        assert module.__package__.startswith(package_name)
