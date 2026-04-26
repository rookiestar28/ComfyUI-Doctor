#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import importlib
import importlib.abc
import importlib.util
import io
import os
import sys
import tempfile
import traceback
import types
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Iterable


PROJECT_ROOT = Path(__file__).resolve().parent.parent
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
    "pipeline.orchestrator",
    "pipeline.plugins",
    "pipeline.stages.pattern_matcher",
    "pipeline.stages.llm_builder",
    "services.job_manager",
    "services.routes",
    "services.intent",
    "services.diagnostics",
    "services.diagnostics.store",
    "services.diagnostics.runner",
    "services.policy",
    "services.providers.base",
    "services.providers.registry",
    "services.prompt_composer",
    "services.log_ring_buffer",
]
SKIP_STATIC_IMPORT_SCAN = {"prestartup_script.py", "verify_routes.py"}
SKIP_SCAN_DIR_NAMES = {"__pycache__", ".venv", ".venv-wsl", "tests", "scripts", "reference", "docs", "web", "node_modules"}
ALLOWED_BARE_INTERNAL_IMPORTS = {"import_compat"}




class _BlockedTopLevelFinder(importlib.abc.MetaPathFinder):
    def __init__(self, blocked_top_levels: set[str]):
        self.blocked_top_levels = blocked_top_levels

    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".")[0] in self.blocked_top_levels:
            raise ModuleNotFoundError(f"Blocked host-like internal import: {fullname}")
        return None


class AsciiOnlyStream(io.StringIO):
    encoding = "cp1252"

    def write(self, message):
        text = str(message)
        text.encode("ascii")
        return super().write(text)

    def isatty(self):
        return False

    def fileno(self):
        raise OSError("No file descriptor available")


def _project_init_path(project_root: Path) -> Path:
    init_path = project_root / "__init__.py"
    if init_path.exists():
        return init_path
    backup_path = project_root / "__init__.py.bak"
    if backup_path.exists():
        return backup_path
    return init_path


def _internal_top_levels(project_root: Path) -> set[str]:
    names = {"services", "pipeline"}
    for path in project_root.glob("*.py"):
        if path.name.startswith("test_"):
            continue
        names.add(path.stem)
    return names


def _should_detach(module_name: str, internal_top_levels: set[str]) -> bool:
    return any(
        module_name == prefix or module_name.startswith(f"{prefix}.")
        for prefix in internal_top_levels
    )


@contextmanager
def synthetic_package_import_context(project_root: Path):
    internal_top_levels = _internal_top_levels(project_root)
    package_name = f"doctor_hostload_{uuid.uuid4().hex}"
    original_sys_path = list(sys.path)
    original_meta_path = list(sys.meta_path)
    detached = {
        name: sys.modules.pop(name)
        for name in list(sys.modules)
        if _should_detach(name, internal_top_levels)
    }

    blocked_finder = _BlockedTopLevelFinder(set(internal_top_levels))
    filtered_path = []
    for entry in original_sys_path:
        try:
            if Path(entry or ".").resolve() == project_root.resolve():
                continue
        except Exception:
            pass
        filtered_path.append(entry)

    try:
        sys.path[:] = filtered_path
        sys.meta_path.insert(0, blocked_finder)
        package = types.ModuleType(package_name)
        package.__file__ = str(_project_init_path(project_root))
        package.__package__ = package_name
        package.__path__ = [str(project_root)]
        sys.modules[package_name] = package
        yield package_name
    finally:
        for name in list(sys.modules):
            if name == package_name or name.startswith(f"{package_name}."):
                sys.modules.pop(name, None)
        sys.modules.update(detached)
        sys.path[:] = original_sys_path
        sys.meta_path[:] = original_meta_path


# IMPORTANT: keep this check host-like. The point is to validate package imports
# without assuming the extension root is a top-level import root.
def check_package_imports(project_root: Path = PROJECT_ROOT, modules: Iterable[str] = PACKAGE_MODULES) -> list[str]:
    issues: list[str] = []
    with synthetic_package_import_context(project_root) as package_name:
        for module_name in modules:
            try:
                module = importlib.import_module(f"{package_name}.{module_name}")
                if module.__name__ != f"{package_name}.{module_name}":
                    issues.append(f"{module_name}: imported as unexpected module name {module.__name__}")
            except Exception as exc:
                issues.append(
                    f"{module_name}: {exc.__class__.__name__}: {exc}"
                )
    return issues


def check_prestartup_bootstrap(project_root: Path = PROJECT_ROOT) -> list[str]:
    issues: list[str] = []
    module_name = f"doctor_prestartup_{uuid.uuid4().hex}"
    script_path = project_root / "prestartup_script.py"
    if not script_path.exists():
        return [f"Missing prestartup script: {script_path}"]

    original_stdout = sys.stdout
    original_stderr = sys.stderr
    original_env = {key: os.environ.get(key) for key in ("COMFYUI_DOCTOR_LOG_PATH", "COMFYUI_DOCTOR_LOG_DIR")}
    ascii_stream = AsciiOnlyStream()
    module = None

    with synthetic_package_import_context(project_root):
        try:
            sys.stdout = ascii_stream
            sys.stderr = ascii_stream
            with tempfile.TemporaryDirectory(prefix="doctor-hostload-") as tmpdir:
                os.environ["COMFYUI_DOCTOR_LOG_DIR"] = tmpdir
                os.environ.pop("COMFYUI_DOCTOR_LOG_PATH", None)
                spec = importlib.util.spec_from_file_location(module_name, script_path)
                if spec is None or spec.loader is None:
                    return [f"Unable to build import spec for {script_path}"]
                module = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = module
                spec.loader.exec_module(module)
        except Exception as exc:
            issues.append(f"prestartup_script.py: {exc.__class__.__name__}: {exc}")
            issues.append(traceback.format_exc(limit=4).strip())
        finally:
            if module is not None and hasattr(module, "PrestartupLogger"):
                try:
                    module.PrestartupLogger.uninstall()
                except Exception:
                    pass
            sys.modules.pop(module_name, None)
            sys.stdout = original_stdout
            sys.stderr = original_stderr
            for key, value in original_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
    return issues


def _iter_product_python_files(project_root: Path) -> Iterable[Path]:
    for path in sorted(project_root.glob("*.py")):
        if path.name not in SKIP_STATIC_IMPORT_SCAN:
            yield path
    for folder_name in ("services", "pipeline"):
        base = project_root / folder_name
        if not base.exists():
            continue
        for path in sorted(base.rglob("*.py")):
            if any(part in SKIP_SCAN_DIR_NAMES for part in path.parts):
                continue
            yield path


def check_import_policy(project_root: Path = PROJECT_ROOT) -> list[str]:
    issues: list[str] = []
    internal_top_levels = _internal_top_levels(project_root)

    for path in _iter_product_python_files(project_root):
        try:
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(path))
        except Exception as exc:
            issues.append(f"{path.relative_to(project_root)}: failed to parse source: {exc}")
            continue

        relative_modules: set[str] = set()
        absolute_modules: list[tuple[int, str]] = []

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if not node.module:
                    continue
                first = node.module.split(".")[0]
                if first not in internal_top_levels:
                    continue
                if node.level > 0:
                    relative_modules.add(node.module)
                else:
                    absolute_modules.append((node.lineno, node.module))
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    first = alias.name.split(".")[0]
                    if first in internal_top_levels:
                        absolute_modules.append((node.lineno, alias.name))

        for lineno, module_name in absolute_modules:
            if module_name in ALLOWED_BARE_INTERNAL_IMPORTS:
                continue
            if module_name not in relative_modules:
                issues.append(
                    f"{path.relative_to(project_root)}:{lineno}: bare internal import '{module_name}' without relative-first fallback"
                )
    return issues


def run_all_checks(project_root: Path = PROJECT_ROOT) -> dict[str, list[str]]:
    return {
        "package_imports": check_package_imports(project_root),
        "prestartup_bootstrap": check_prestartup_bootstrap(project_root),
        "import_policy": check_import_policy(project_root),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate host-like ComfyUI package/startup loading behavior.")
    parser.add_argument("--project-root", default=str(PROJECT_ROOT), help="Project root to validate")
    args = parser.parse_args(argv)

    project_root = Path(args.project_root).resolve()
    results = run_all_checks(project_root)

    print(f"[host-load] Validating project root: {project_root}")
    had_errors = False
    for check_name, issues in results.items():
        if issues:
            had_errors = True
            print(f"[host-load] FAIL {check_name}: {len(issues)} issue(s)")
            for issue in issues:
                print(f"[host-load]   - {issue}")
        else:
            print(f"[host-load] PASS {check_name}")

    if had_errors:
        print("[host-load] Host-like validation failed.")
        return 1

    print("[host-load] All host-like package/startup checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
