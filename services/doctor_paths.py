"""
doctor_paths.py

Canonical Data Directory Resolver for ComfyUI-Doctor.

This module is responsible for determining the safe, permanent location for:
- error_history.json (HistoryStore)
- Doctor debug logs
- Any other persisted state

It prioritizes ComfyUI's private system-user directory when available, with
legacy user-directory fallbacks for older hosts and Desktop resource layouts.
"""

import logging
import os
import shutil
import sys
import tempfile

try:
    import folder_paths
except ImportError:
    folder_paths = None

# Fallback logger if main logger not set up
logger = logging.getLogger("ComfyUI-Doctor.paths")

_DOCTOR_SYSTEM_USER_NAME = "comfyui_doctor"
_DOCTOR_LEGACY_USER_DIR_NAME = "ComfyUI-Doctor"


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


def _detect_desktop_base_path_from_python(python_executable: str | None = None) -> str | None:
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


def _detect_comfy_root_from_extension(module_file: str | None = None) -> str | None:
    """Infer portable/git-clone ComfyUI root from extension layout."""
    current_file = os.path.abspath(module_file or __file__)
    services_dir = os.path.dirname(current_file)
    extension_root = os.path.dirname(services_dir)
    custom_nodes_dir = os.path.dirname(extension_root)

    if os.path.basename(custom_nodes_dir).lower() != "custom_nodes":
        return None

    return os.path.dirname(custom_nodes_dir)


def _detect_extension_root(module_file: str | None = None) -> str:
    """Return the extension repository root containing the services package."""
    current_file = os.path.abspath(module_file or __file__)
    return os.path.dirname(os.path.dirname(current_file))


def _same_path(left: str | None, right: str | None) -> bool:
    if not left or not right:
        return False
    return os.path.normcase(os.path.abspath(left)) == os.path.normcase(os.path.abspath(right))


def _is_desktop_runtime_proven(
    desktop_base_path: str | None,
    portable_comfy_root: str | None,
    portable_is_desktop_resources: bool,
) -> bool:
    """Reject `.venv`-only Desktop guesses when explicit development evidence conflicts."""
    if not desktop_base_path:
        return False

    # IMPORTANT: a repository-local venv has the same suffix as Desktop's
    # managed interpreter and must not change the runtime identity.
    if _same_path(desktop_base_path, _detect_extension_root()):
        return False

    # An ordinary custom_nodes tree outside Desktop Resources is explicit
    # portable/git evidence. Ambiguous layouts fail open to that identity.
    return not (portable_comfy_root and not portable_is_desktop_resources)


def get_path_diagnostics() -> dict[str, str | None]:
    """Return independent runtime-identity and storage-source diagnostics."""
    folder_user_directory = None
    folder_system_user_directory = None
    if folder_paths and hasattr(folder_paths, "get_system_user_directory"):
        try:
            folder_system_user_directory = folder_paths.get_system_user_directory(_DOCTOR_SYSTEM_USER_NAME)
        except Exception as exc:
            logger.debug(f"Failed to get_system_user_directory for diagnostics: {exc}")

    if folder_paths and hasattr(folder_paths, "get_user_directory"):
        try:
            folder_user_directory = folder_paths.get_user_directory()
        except Exception as exc:
            logger.debug(f"Failed to get_user_directory for diagnostics: {exc}")

    desktop_base_path = _detect_desktop_base_path_from_python()
    portable_comfy_root = _detect_comfy_root_from_extension()
    portable_is_desktop_resources = is_desktop_resources_path(portable_comfy_root or "")
    desktop_runtime_proven = _is_desktop_runtime_proven(
        desktop_base_path,
        portable_comfy_root,
        portable_is_desktop_resources,
    )

    if desktop_runtime_proven:
        install_mode = "desktop"
        source = "python_executable:.venv"
    elif folder_system_user_directory:
        install_mode = "standard"
        source = "folder_paths.get_system_user_directory"
    elif folder_user_directory:
        install_mode = "standard"
        source = "folder_paths.get_user_directory"
    elif portable_comfy_root:
        install_mode = "portable_or_git"
        source = "extension_layout:custom_nodes"
    else:
        install_mode = "unknown"
        source = "fallback"

    if folder_system_user_directory:
        storage_source = "folder_paths.get_system_user_directory"
    elif folder_user_directory:
        storage_source = "folder_paths.get_user_directory"
    elif portable_comfy_root and not portable_is_desktop_resources:
        storage_source = "extension_layout:custom_nodes"
    elif desktop_runtime_proven:
        storage_source = "python_executable:.venv"
    elif portable_comfy_root:
        storage_source = "extension_layout:custom_nodes"
    else:
        storage_source = "fallback"

    return {
        "install_mode": install_mode,
        "source": source,
        "storage_source": storage_source,
        "folder_system_user_directory": folder_system_user_directory,
        "folder_user_directory": folder_user_directory,
        "desktop_base_path": desktop_base_path,
        "portable_comfy_root": portable_comfy_root,
        "python_executable": sys.executable,
    }


def _copy_missing_legacy_data(source_dir: str | None, target_dir: str | None) -> None:
    """Best-effort copy of legacy public-user state into the private system-user dir."""
    if not source_dir or not target_dir:
        return

    source_abs = os.path.abspath(source_dir)
    target_abs = os.path.abspath(target_dir)
    if os.path.normcase(source_abs) == os.path.normcase(target_abs):
        return
    if not os.path.isdir(source_abs):
        return
    if is_desktop_resources_path(source_abs) or is_desktop_resources_path(target_abs):
        return

    try:
        if os.path.commonpath([source_abs, target_abs]) == source_abs:
            logger.debug("Skipping legacy state migration because target is inside source")
            return
    except ValueError:
        return

    try:
        for root, dirs, files in os.walk(source_abs, topdown=True):
            # SECURITY: do not follow symlinks while copying legacy user data into private state.
            dirs[:] = [dirname for dirname in dirs if not os.path.islink(os.path.join(root, dirname))]
            relative_root = os.path.relpath(root, source_abs)
            destination_root = target_abs if relative_root == "." else os.path.join(target_abs, relative_root)
            os.makedirs(destination_root, exist_ok=True)

            for filename in files:
                source_file = os.path.join(root, filename)
                if os.path.islink(source_file):
                    continue

                destination_file = os.path.join(destination_root, filename)
                if os.path.exists(destination_file):
                    continue

                shutil.copy2(source_file, destination_file)
    except Exception as exc:
        logger.debug(f"Best-effort legacy state migration failed: {exc}")


def get_doctor_data_dir() -> str:
    """
    Resolve the canonical data directory for ComfyUI-Doctor.

    Priority Order:
    1. ComfyUI system-user directory (`folder_paths.get_system_user_directory()`)
    2. Legacy ComfyUI User Directory (`folder_paths.get_user_directory()/ComfyUI-Doctor`)
    3. Portable / Git clone sibling (`<ComfyUI root>/user/ComfyUI-Doctor`)
    4. Legacy portable fallback (`<ComfyUI root>/user_data/ComfyUI-Doctor`)
    5. Desktop base path inferred from managed `.venv` (`<basePath>/user/ComfyUI-Doctor`)
    6. Extension-local logs (only when not inside Desktop resources)
    7. OS Temporary Directory

    Returns:
        Absolute path to a writable directory.
    """
    candidates = []
    seen = set()
    system_user_dir = None
    legacy_user_dir = None

    def add_candidate(path: str | None) -> None:
        if not path:
            return
        normalized = os.path.normcase(os.path.abspath(path))
        if normalized in seen:
            return
        seen.add(normalized)
        candidates.append(path)

    # 1. ComfyUI system-user directory (private host state on current ComfyUI)
    if folder_paths and hasattr(folder_paths, "get_system_user_directory"):
        try:
            system_user_dir = folder_paths.get_system_user_directory(_DOCTOR_SYSTEM_USER_NAME)
            add_candidate(system_user_dir)
        except Exception as exc:
            logger.debug(f"Failed to get_system_user_directory: {exc}")

    # 2. ComfyUI User Directory (legacy fallback when folder_paths is available)
    if folder_paths and hasattr(folder_paths, "get_user_directory"):
        try:
            user_dir = folder_paths.get_user_directory()
            if user_dir:
                legacy_user_dir = os.path.join(user_dir, _DOCTOR_LEGACY_USER_DIR_NAME)
                add_candidate(legacy_user_dir)
        except Exception as exc:
            logger.debug(f"Failed to get_user_directory: {exc}")

    # 3/4/5. Desktop vs portable/git-clone fallback ordering
    # IMPORTANT: when the extension path clearly resolves through a real
    # `custom_nodes` layout outside Desktop resources, prefer that portable/git
    # root over the current Python `.venv` heuristic. This avoids false Desktop
    # detection during repo-local test/dev environments that also use `.venv`.
    desktop_base_path = _detect_desktop_base_path_from_python()
    try:
        comfy_root = _detect_comfy_root_from_extension()
        portable_is_desktop_resources = is_desktop_resources_path(comfy_root or "")

        if comfy_root and not portable_is_desktop_resources:
            add_candidate(os.path.join(comfy_root, "user", _DOCTOR_LEGACY_USER_DIR_NAME))
            add_candidate(os.path.join(comfy_root, "user_data", _DOCTOR_LEGACY_USER_DIR_NAME))

        if desktop_base_path:
            add_candidate(os.path.join(desktop_base_path, "user", _DOCTOR_LEGACY_USER_DIR_NAME))

        if comfy_root and portable_is_desktop_resources:
            add_candidate(os.path.join(comfy_root, "user", _DOCTOR_LEGACY_USER_DIR_NAME))
            add_candidate(os.path.join(comfy_root, "user_data", _DOCTOR_LEGACY_USER_DIR_NAME))

        if comfy_root:
            legacy_internal = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
            if not is_desktop_resources_path(legacy_internal):
                add_candidate(legacy_internal)
    except Exception:
        pass

    # 7. OS Temp (Last Resort)
    add_candidate(os.path.join(tempfile.gettempdir(), _DOCTOR_LEGACY_USER_DIR_NAME))

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
            if system_user_dir and os.path.normcase(os.path.abspath(path)) == os.path.normcase(
                os.path.abspath(system_user_dir)
            ):
                _copy_missing_legacy_data(legacy_user_dir, system_user_dir)
            return path
        except Exception as exc:
            logger.debug(f"Candidate path {path} failed: {exc}")
            continue

    return os.path.join(tempfile.gettempdir(), _DOCTOR_LEGACY_USER_DIR_NAME)
