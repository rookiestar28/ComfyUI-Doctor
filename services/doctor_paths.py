"""
doctor_paths.py

Canonical Data Directory Resolver for ComfyUI-Doctor.

This module is responsible for determining the safe, permanent location for:
- error_history.json (HistoryStore)
- Doctor debug logs
- Any other persisted state

It prioritizes the standard ComfyUI user directory to ensure compatibility
with ComfyUI Desktop (which often makes the custom_nodes directory read-only
or ephemeral in 'resources/').
"""

import logging
import os
import sys
import tempfile
from typing import Dict, Optional

try:
    import folder_paths
except ImportError:
    folder_paths = None

# Fallback logger if main logger not set up
logger = logging.getLogger("ComfyUI-Doctor.paths")


_DESKTOP_RESOURCE_INDICATORS = [
    os.path.join("resources", "app"),
    os.path.join("resources", "comfyui"),
    os.path.join("resources", "app.asar"),
    os.path.join("resources", "app.asar.unpacked"),
    "resources\\app",
    "resources\\comfyui",
    "resources\\app.asar",
    "resources\\app.asar.unpacked",
]


def is_desktop_resources_path(path: str) -> bool:
    """
    Heuristic to detect if a path is inside ComfyUI Desktop's 'resources' folder.
    Writing here is dangerous as it may be overwritten on update or is logically read-only.
    """
    if not path:
        return False

    normalized = os.path.normpath(path).lower()
    return any(indicator in normalized for indicator in _DESKTOP_RESOURCE_INDICATORS)


def _detect_desktop_base_path_from_python(python_executable: Optional[str] = None) -> Optional[str]:
    """Infer ComfyUI Desktop basePath from the managed `.venv` interpreter layout.

    Upstream Desktop now keeps Python at:
    - `<basePath>/.venv/Scripts/python.exe` (Windows)
    - `<basePath>/.venv/bin/python` (POSIX)
    """
    executable = os.path.abspath(python_executable or sys.executable or "")
    if not executable:
        return None

    filename = os.path.basename(executable).lower()
    env_bin = os.path.basename(os.path.dirname(executable)).lower()
    env_root = os.path.basename(os.path.dirname(os.path.dirname(executable))).lower()

    if not filename.startswith("python"):
        return None
    if env_bin not in {"bin", "scripts"}:
        return None
    if env_root != ".venv":
        return None

    return os.path.dirname(os.path.dirname(os.path.dirname(executable)))


def _detect_comfy_root_from_extension(module_file: Optional[str] = None) -> Optional[str]:
    """Infer portable/git-clone ComfyUI root from extension layout."""
    current_file = os.path.abspath(module_file or __file__)
    services_dir = os.path.dirname(current_file)
    extension_root = os.path.dirname(services_dir)
    custom_nodes_dir = os.path.dirname(extension_root)

    if os.path.basename(custom_nodes_dir).lower() != "custom_nodes":
        return None

    return os.path.dirname(custom_nodes_dir)


def get_path_diagnostics() -> Dict[str, Optional[str]]:
    """Return best-effort install-mode diagnostics for health/debug output."""
    folder_user_directory = None
    if folder_paths and hasattr(folder_paths, "get_user_directory"):
        try:
            folder_user_directory = folder_paths.get_user_directory()
        except Exception as exc:
            logger.debug(f"Failed to get_user_directory for diagnostics: {exc}")

    desktop_base_path = _detect_desktop_base_path_from_python()
    portable_comfy_root = _detect_comfy_root_from_extension()

    if folder_user_directory:
        install_mode = "standard"
        source = "folder_paths.get_user_directory"
    elif desktop_base_path:
        install_mode = "desktop"
        source = "python_executable:.venv"
    elif portable_comfy_root:
        install_mode = "portable_or_git"
        source = "extension_layout:custom_nodes"
    else:
        install_mode = "unknown"
        source = "fallback"

    return {
        "install_mode": install_mode,
        "source": source,
        "folder_user_directory": folder_user_directory,
        "desktop_base_path": desktop_base_path,
        "portable_comfy_root": portable_comfy_root,
        "python_executable": sys.executable,
    }


def get_doctor_data_dir() -> str:
    """
    Resolve the canonical data directory for ComfyUI-Doctor.

    Priority Order:
    1. ComfyUI User Directory (`folder_paths.get_user_directory()`)
    2. Desktop base path inferred from managed `.venv` (`<basePath>/user/ComfyUI-Doctor`)
    3. Portable / Git clone sibling (`<ComfyUI root>/user/ComfyUI-Doctor`)
    4. Legacy portable fallback (`<ComfyUI root>/user_data/ComfyUI-Doctor`)
    5. Extension-local logs (only when not inside Desktop resources)
    6. OS Temporary Directory

    Returns:
        Absolute path to a writable directory.
    """
    candidates = []
    seen = set()

    def add_candidate(path: Optional[str]) -> None:
        if not path:
            return
        normalized = os.path.normcase(os.path.abspath(path))
        if normalized in seen:
            return
        seen.add(normalized)
        candidates.append(path)

    # 1. ComfyUI User Directory (Best when folder_paths is available)
    if folder_paths and hasattr(folder_paths, "get_user_directory"):
        try:
            user_dir = folder_paths.get_user_directory()
            if user_dir:
                add_candidate(os.path.join(user_dir, "ComfyUI-Doctor"))
        except Exception as exc:
            logger.debug(f"Failed to get_user_directory: {exc}")

    # 2. Desktop basePath inferred from the managed `.venv`
    desktop_base_path = _detect_desktop_base_path_from_python()
    if desktop_base_path:
        add_candidate(os.path.join(desktop_base_path, "user", "ComfyUI-Doctor"))

    # 3/4. Portable or git-clone layout inferred from extension location
    try:
        comfy_root = _detect_comfy_root_from_extension()
        if comfy_root:
            add_candidate(os.path.join(comfy_root, "user", "ComfyUI-Doctor"))
            add_candidate(os.path.join(comfy_root, "user_data", "ComfyUI-Doctor"))

            legacy_internal = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
            if not is_desktop_resources_path(legacy_internal):
                add_candidate(legacy_internal)
    except Exception:
        pass

    # 5. OS Temp (Last Resort)
    add_candidate(os.path.join(tempfile.gettempdir(), "ComfyUI-Doctor"))

    for path in candidates:
        try:
            if is_desktop_resources_path(path):
                logger.debug(f"Skipping potential resources path: {path}")
                continue

            os.makedirs(path, exist_ok=True)
            test_file = os.path.join(path, ".write_test")
            with open(test_file, "w", encoding="utf-8") as handle:
                handle.write("ok")
            os.remove(test_file)
            return path
        except Exception as exc:
            logger.debug(f"Candidate path {path} failed: {exc}")
            continue

    return os.path.join(tempfile.gettempdir(), "ComfyUI-Doctor")
