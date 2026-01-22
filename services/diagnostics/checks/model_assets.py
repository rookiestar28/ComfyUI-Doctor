"""
F14 Proactive Diagnostics - Model Assets Check

Analyzes workflow to detect:
1. File paths in widget values (models, images, etc.)
2. Validate existence and readability
"""

import logging
import os
import re
from pathlib import Path
from typing import Dict, Any, List, Set, Optional, Tuple

from ..models import (
    HealthIssue,
    HealthCheckRequest,
    IssueCategory,
    IssueSeverity,
    IssueTarget,
)
from . import register_check

logger = logging.getLogger("comfyui-doctor.diagnostics.checks.model_assets")


# ============================================================================
# Configuration
# ============================================================================

# Node types that typically load files from disk
FILE_LOADING_NODE_TYPES: Set[str] = {
    # Model loaders
    "CheckpointLoaderSimple", "CheckpointLoader",
    "VAELoader", "CLIPLoader", "LoraLoader", "LoraLoaderModelOnly",
    "ControlNetLoader", "StyleModelLoader", "CLIPVisionLoader",
    "UpscaleModelLoader", "GLIGENLoader", "HypernetworkLoader",
    "UNETLoader", "DualCLIPLoader", "TripleCLIPLoader",
    # Image loaders
    "LoadImage", "LoadImageMask", "LoadLatent",
    # Video loaders (common custom nodes)
    "VHS_LoadVideo", "LoadVideo",
    # IP-Adapter loaders
    "IPAdapterModelLoader", "IPAdapterFaceIDLoader",
}

# Widget names that typically contain file paths
PATH_WIDGET_NAMES: Set[str] = {
    "ckpt_name", "vae_name", "clip_name", "lora_name",
    "control_net_name", "style_model_name", "upscale_model_name",
    "model_name", "image", "video", "latent_file",
    "filename", "file", "path", "image_path", "video_path",
}

# Common model file extensions
MODEL_EXTENSIONS: Set[str] = {
    ".safetensors", ".ckpt", ".pt", ".pth", ".bin",
    ".onnx", ".pkl", ".pickle",
}

# Common image/media extensions
MEDIA_EXTENSIONS: Set[str] = {
    ".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tiff",
    ".mp4", ".webm", ".avi", ".mov", ".mkv",
}


# ============================================================================
# ComfyUI Folder Detection
# ============================================================================

_comfy_paths: Optional[Dict[str, List[Path]]] = None


def _get_comfy_model_paths() -> Dict[str, List[Path]]:
    """Get ComfyUI model folder paths."""
    global _comfy_paths
    if _comfy_paths is not None:
        return _comfy_paths

    paths: Dict[str, List[Path]] = {
        "checkpoints": [],
        "vae": [],
        "loras": [],
        "controlnet": [],
        "clip": [],
        "upscale_models": [],
        "embeddings": [],
        "input": [],
        "output": [],
    }

    # Try to get paths from ComfyUI's folder_paths
    try:
        import folder_paths

        # Map our categories to folder_paths functions
        path_mappings = {
            "checkpoints": "checkpoints",
            "vae": "vae",
            "loras": "loras",
            "controlnet": "controlnet",
            "clip": "clip",
            "upscale_models": "upscale_models",
            "embeddings": "embeddings",
        }

        for key, folder_name in path_mappings.items():
            try:
                folder_list = folder_paths.get_folder_paths(folder_name)
                paths[key] = [Path(p) for p in folder_list if p]
            except Exception:
                pass

        # Input/output folders
        try:
            paths["input"] = [Path(folder_paths.get_input_directory())]
        except Exception:
            pass

        try:
            paths["output"] = [Path(folder_paths.get_output_directory())]
        except Exception:
            pass

    except ImportError:
        logger.debug("folder_paths not available, using fallback detection")

    _comfy_paths = paths
    return paths


def _clear_path_cache():
    """Clear path cache (for testing)."""
    global _comfy_paths
    _comfy_paths = None


def _find_file_in_comfy_paths(
    filename: str,
    category: str = "checkpoints",
) -> Tuple[bool, Optional[Path]]:
    """
    Try to find a file in ComfyUI's model paths.

    Returns:
        (found, full_path) - found is True if file exists, full_path is the resolved path
    """
    paths = _get_comfy_model_paths()
    search_paths = paths.get(category, [])

    # Also search common parent directories
    for search_path in search_paths:
        if not search_path.exists():
            continue

        # Direct match
        full_path = search_path / filename
        if full_path.exists():
            return True, full_path

        # Check subdirectories (one level)
        try:
            for subdir in search_path.iterdir():
                if subdir.is_dir():
                    full_path = subdir / filename
                    if full_path.exists():
                        return True, full_path
        except (PermissionError, OSError):
            continue

    return False, None


def _is_path_like(value: str) -> bool:
    """Heuristic to determine if a string looks like a file path."""
    if not isinstance(value, str) or len(value) < 3:
        return False

    # Check for common path patterns
    # Has extension that looks like a model or media file
    lower = value.lower()
    for ext in MODEL_EXTENSIONS | MEDIA_EXTENSIONS:
        if lower.endswith(ext):
            return True

    # Contains path separators
    if "/" in value or "\\" in value:
        return True

    # Ends with common model naming patterns
    if re.search(r"[-_]v?\d+(\.\d+)?$", value):
        return True

    return False


def _sanitize_path_for_display(path: str, max_len: int = 50) -> str:
    """Sanitize path for display (remove potentially sensitive parts)."""
    # Only show filename, not full path (privacy)
    try:
        p = Path(path)
        name = p.name
        if len(name) > max_len:
            return name[:max_len-3] + "..."
        return name
    except Exception:
        if len(path) > max_len:
            return path[:max_len-3] + "..."
        return path


# ============================================================================
# Check Implementation
# ============================================================================

@register_check("model_assets")
async def check_model_assets(
    workflow: Dict[str, Any],
    request: HealthCheckRequest,
) -> List[HealthIssue]:
    """
    Check model and asset file availability.

    Returns list of HealthIssues for missing or inaccessible files.
    """
    issues: List[HealthIssue] = []

    nodes = workflow.get("nodes", [])
    if not isinstance(nodes, list):
        return issues

    # Track checked paths to avoid duplicates
    checked_paths: Set[str] = set()

    for node in nodes:
        if not isinstance(node, dict):
            continue

        node_id = node.get("id")
        node_type = node.get("type", "")
        node_title = node.get("title", node_type)
        widgets_values = node.get("widgets_values", [])

        if not isinstance(widgets_values, list):
            continue

        # Determine if this node type is known to load files
        is_file_loader = any(
            loader in node_type for loader in FILE_LOADING_NODE_TYPES
        )

        # Check each widget value
        for idx, value in enumerate(widgets_values):
            if not isinstance(value, str):
                continue

            # Skip if already checked
            if value in checked_paths:
                continue

            # Determine if this looks like a file path
            if not _is_path_like(value):
                continue

            checked_paths.add(value)

            # Determine category for path lookup
            category = _determine_asset_category(node_type, value)

            # Try to find the file
            found, full_path = _find_file_in_comfy_paths(value, category)

            # Also check if it's an absolute path that exists
            if not found:
                try:
                    p = Path(value)
                    if p.is_absolute() and p.exists():
                        found = True
                        full_path = p
                except Exception:
                    pass

            if not found:
                # File not found - report issue
                target = IssueTarget(node_id=node_id)

                # Severity depends on whether this is a known file loader
                severity = IssueSeverity.WARNING if is_file_loader else IssueSeverity.INFO

                safe_name = _sanitize_path_for_display(value)

                issues.append(HealthIssue(
                    issue_id=HealthIssue.generate_issue_id(
                        "missing_asset", target, value[:32]
                    ),
                    category=IssueCategory.MODEL,
                    severity=severity,
                    title="Asset File Not Found",
                    summary=f"Node '{node_title}' (#{node_id}) references file '{safe_name}' which cannot be found",
                    evidence=[
                        f"Filename: {safe_name}",
                        f"Node type: {node_type}",
                        f"Searched in: {category} folders",
                    ],
                    recommendation=[
                        f"Ensure the file '{safe_name}' exists in the appropriate ComfyUI folder",
                        "Check if the file was moved, renamed, or deleted",
                        "Verify the file name spelling (case-sensitive on some systems)",
                    ],
                    target=target,
                ))
            else:
                # File found - check if readable
                if full_path:
                    readable_issue = _check_file_readable(
                        full_path, node_id, node_title, node_type, value
                    )
                    if readable_issue:
                        issues.append(readable_issue)

    return issues


def _determine_asset_category(node_type: str, filename: str) -> str:
    """Determine the asset category based on node type and filename."""
    lower_type = node_type.lower()
    lower_file = filename.lower()

    if "checkpoint" in lower_type or "ckpt" in lower_file:
        return "checkpoints"
    if "vae" in lower_type:
        return "vae"
    if "lora" in lower_type:
        return "loras"
    if "controlnet" in lower_type:
        return "controlnet"
    if "clip" in lower_type:
        return "clip"
    if "upscale" in lower_type:
        return "upscale_models"
    if "embed" in lower_type:
        return "embeddings"
    if "loadimage" in lower_type or any(lower_file.endswith(ext) for ext in MEDIA_EXTENSIONS):
        return "input"

    # Default to checkpoints for unknown model loaders
    return "checkpoints"


def _check_file_readable(
    path: Path,
    node_id: int,
    node_title: str,
    node_type: str,
    original_value: str,
) -> Optional[HealthIssue]:
    """Check if a file is readable."""
    try:
        # Try to open for reading
        with open(path, "rb") as f:
            # Read first byte to verify access
            f.read(1)
        return None  # File is readable
    except PermissionError:
        target = IssueTarget(node_id=node_id)
        safe_name = _sanitize_path_for_display(original_value)
        return HealthIssue(
            issue_id=HealthIssue.generate_issue_id(
                "asset_permission", target, original_value[:32]
            ),
            category=IssueCategory.MODEL,
            severity=IssueSeverity.WARNING,
            title="Asset File Not Readable",
            summary=f"Node '{node_title}' (#{node_id}) references file '{safe_name}' which cannot be read (permission denied)",
            evidence=[
                f"Filename: {safe_name}",
                "File exists but cannot be read",
                "This may be a permission issue",
            ],
            recommendation=[
                "Check file permissions",
                "Ensure ComfyUI has read access to the file",
            ],
            target=target,
        )
    except Exception as e:
        target = IssueTarget(node_id=node_id)
        safe_name = _sanitize_path_for_display(original_value)
        return HealthIssue(
            issue_id=HealthIssue.generate_issue_id(
                "asset_error", target, original_value[:32]
            ),
            category=IssueCategory.MODEL,
            severity=IssueSeverity.INFO,
            title="Asset File Access Error",
            summary=f"Node '{node_title}' (#{node_id}) references file '{safe_name}' which cannot be accessed",
            evidence=[
                f"Filename: {safe_name}",
                f"Error: {type(e).__name__}",
            ],
            recommendation=[
                "Verify the file is not corrupted",
                "Try redownloading the file if issues persist",
            ],
            target=target,
        )
