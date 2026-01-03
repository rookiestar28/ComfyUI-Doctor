"""
Pytest configuration for ComfyUI-Doctor tests.

CRITICAL: This conftest.py prevents pytest from treating the project root as a Python package.

Problem:
  - ComfyUI-Doctor/__init__.py uses relative imports (from .logger import ...)
  - These only work when the module is imported as part of a package (e.g., custom_nodes.ComfyUI-Doctor)
  - Pytest tries to import __init__.py directly, causing "no known parent package" errors

Solution:
  - Tell pytest to NOT treat the root directory as a package
  - Rename root __init__.py temporarily during test collection

Last Modified: 2026-01-03 (Fixed CI import errors)
"""

import sys
from pathlib import Path

# Add project root to sys.path for absolute imports
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

def pytest_ignore_collect(collection_path, config):
    """
    Prevent pytest from collecting __init__.py in the project root.

    This prevents the "attempted relative import with no known parent package" error
    that occurs when pytest tries to import __init__.py as a standalone module.
    """
    if collection_path.name == "__init__.py" and collection_path.parent == project_root:
        return True
    return False

def pytest_configure(config):
    """
    Rename root __init__.py before test collection to prevent pytest from treating root as package.
    """
    root_init = project_root / "__init__.py"
    backup_init = project_root / "__init__.py.bak"

    if root_init.exists() and not backup_init.exists():
        root_init.rename(backup_init)
        config._comfyui_doctor_init_renamed = True
    else:
        config._comfyui_doctor_init_renamed = False

def pytest_unconfigure(config):
    """
    Restore root __init__.py after tests complete.
    """
    if getattr(config, '_comfyui_doctor_init_renamed', False):
        root_init = project_root / "__init__.py"
        backup_init = project_root / "__init__.py.bak"

        if backup_init.exists():
            backup_init.rename(root_init)

