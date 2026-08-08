"""
Pytest configuration for ComfyUI-Doctor tests.

CRITICAL: This conftest.py prevents pytest from collecting the project entrypoint.

Problem:
  - ComfyUI-Doctor/__init__.py uses relative imports (from .logger import ...)
  - These only work when the module is imported as part of a package (e.g., custom_nodes.ComfyUI-Doctor)
  - Pytest tries to import __init__.py directly, causing "no known parent package" errors

Solution:
  - Tell pytest to NOT collect the root __init__.py
  - Keep collection isolated to tests without mutating production source

Last Modified: 2026-08-08 (Removed production-entrypoint mutation)
"""

import sys
import types
from pathlib import Path

# Add project root to sys.path for absolute imports
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

_root_collection_sentinel = None


def pytest_sessionstart(session):
    """Keep pytest Package.setup from executing the production entrypoint."""
    global _root_collection_sentinel
    module_name = "__init__"
    existing = sys.modules.get(module_name)
    if existing is not None:
        existing_file = getattr(existing, "__file__", None)
        if existing_file != str(project_root / "__init__.py"):
            raise RuntimeError(f"Unexpected preloaded test module: {module_name}")
        _root_collection_sentinel = existing
        return

    # CRITICAL: pytest's importlib fallback names this invalid-directory package
    # `__init__`; the inert process-local sentinel prevents production startup.
    sentinel = types.ModuleType(module_name)
    sentinel.__file__ = str(project_root / "__init__.py")
    sentinel.__package__ = ""
    sys.modules[module_name] = sentinel
    _root_collection_sentinel = sentinel


def pytest_sessionfinish(session, exitstatus):
    if sys.modules.get("__init__") is _root_collection_sentinel:
        sys.modules.pop("__init__", None)


def pytest_ignore_collect(collection_path, config):
    """
    Prevent pytest from collecting __init__.py in the project root.
    """
    if collection_path.name == "__init__.py" and collection_path.parent == project_root:
        return True
    return False
