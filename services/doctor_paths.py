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

import os
import sys
import tempfile
import logging

try:
    import folder_paths
except ImportError:
    folder_paths = None

# Fallback logger if main logger not set up
logger = logging.getLogger("ComfyUI-Doctor.paths")


def is_desktop_resources_path(path: str) -> bool:
    """
    Heuristic to detect if a path is inside ComfyUI Desktop's 'resources' folder.
    Writing here is dangerous as it may be overwritten on update or is logically read-only.
    """
    if not path:
        return False
    
    normalized = os.path.normpath(path).lower()
    
    # Common desktop patterns
    indicators = [
        os.path.join("resources", "app"),
        os.path.join("resources", "comfyui"),
        os.path.join("resources\\app"),
        os.path.join("resources\\comfyui"),
    ]
    
    return any(ind in normalized for ind in indicators)


def get_doctor_data_dir() -> str:
    """
    Resolve the canonical data directory for ComfyUI-Doctor.
    
    Priority Order:
    1. ComfyUI User Directory (`folder_paths.get_user_directory()`)
       - This is standard for ComfyUI Desktop and modern installs.
    2. 'user_data' folder sibling to custom_nodes (Legacy Portable / Git Clone)
       - If we are in `.../ComfyUI/custom_nodes/ComfyUI-Doctor`, we want `.../ComfyUI/user_data/doctor`.
    3. OS Temporary Directory (Safe Fallback)
       - If all else fails, use system temp.
       
    Returns:
        Absolute path to a writable directory.
    """
    candidates = []

    # 1. ComfyUI User Directory (Best for Desktop & Standard)
    if folder_paths and hasattr(folder_paths, "get_user_directory"):
        try:
            user_dir = folder_paths.get_user_directory()
            if user_dir:
                # Subfolder for clean organization
                candidates.append(os.path.join(user_dir, "ComfyUI-Doctor"))
        except Exception as e:
            logger.debug(f"Failed to get_user_directory: {e}")

    # 2. Portable / Git Clone Sibling Strategy
    # Current: .../ComfyUI/custom_nodes/ComfyUI-Doctor/services/doctor_paths.py
    # Desired: .../ComfyUI/user_data/doctor
    try:
        current_file = os.path.abspath(__file__)
        services_dir = os.path.dirname(current_file)
        root_dir = os.path.dirname(services_dir) # ComfyUI-Doctor
        custom_nodes_dir = os.path.dirname(root_dir) # custom_nodes
        comfy_root = os.path.dirname(custom_nodes_dir) # ComfyUI
        
        # We try to use 'user_data' in ComfyUI root if it exists or if we can create it
        # This keeps data out of the repo/package itself
        portable_user_data = os.path.join(comfy_root, "user_data", "ComfyUI-Doctor")
        candidates.append(portable_user_data)
        
        # Also fall back to internal logs if we really have to (legacy behavior), 
        # but check if it looks like a safe location (not resources)
        legacy_internal = os.path.join(root_dir, "logs")
        if not is_desktop_resources_path(legacy_internal):
            candidates.append(legacy_internal)
            
    except Exception:
        pass

    # 3. OS Temp (Last Resort)
    candidates.append(os.path.join(tempfile.gettempdir(), "ComfyUI-Doctor"))

    # Attempt to create/verify
    for path in candidates:
        try:
            if is_desktop_resources_path(path):
                logger.debug(f"Skipping potential resources path: {path}")
                continue
                
            os.makedirs(path, exist_ok=True)
            
            # Simple write test to confirm it's actually writable
            test_file = os.path.join(path, ".write_test")
            with open(test_file, 'w') as f:
                f.write("ok")
            os.remove(test_file)
            
            return path
        except Exception as e:
            logger.debug(f"Candidate path {path} failed: {e}")
            continue

    # Should generally be unreachable due to tempdir fallback, but minimal fail-safe:
    return os.path.join(tempfile.gettempdir(), "ComfyUI-Doctor")
