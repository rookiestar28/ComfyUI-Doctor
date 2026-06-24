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
    "UNETLoader", "DiffusersLoader",
    "DualCLIPLoader", "TripleCLIPLoader", "QuadrupleCLIPLoader",
    "PhotoMakerLoader", "LoadBackgroundRemovalModel",
    "FrameInterpolationModelLoader", "OpticalFlowLoader",
    "AudioEncoderLoader", "ModelPatchLoader",
    "LoadMoGeModel", "LoadMediaPipeFaceLandmarker",
    # Image loaders
    "LoadImage", "LoadImageMask", "LoadLatent", "Load3D", "Load3DAdvanced",
    # Video loaders (common custom nodes)
    "VHS_LoadVideo", "LoadVideo",
    # IP-Adapter loaders
    "IPAdapterModelLoader", "IPAdapterFaceIDLoader",
}

# Widget names that typically contain file paths
PATH_WIDGET_NAMES: Set[str] = {
    "ckpt_name", "vae_name", "clip_name", "lora_name",
    "control_net_name", "style_model_name", "upscale_model_name",
    "model_name", "model_path", "model_file", "gligen_name",
    "clip_name1", "clip_name2", "clip_name3", "clip_name4",
    "unet_name", "image", "video", "latent_file",
    "filename", "file", "path", "image_path", "video_path",
}

# Common model file extensions
MODEL_EXTENSIONS: Set[str] = {
    ".safetensors", ".ckpt", ".pt", ".pth", ".bin",
    ".onnx", ".pkl", ".pickle", ".tflite", ".task",
}

# Common image/media extensions
MEDIA_EXTENSIONS: Set[str] = {
    ".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tiff",
    ".mp4", ".webm", ".avi", ".mov", ".mkv",
}

# Host Load3D assets live under input/3d and use these first-party extensions.
THREE_D_EXTENSIONS: Set[str] = {
    ".gltf", ".glb", ".obj", ".fbx", ".stl",
    ".spz", ".splat", ".ply", ".ksplat",
}

FOLDER_ASSET_CATEGORIES: Set[str] = {"diffusers"}

INPUT_3D_PREFIX = "3d/"


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
        "text_encoders": [],
        "clip_vision": [],
        "style_models": [],
        "diffusion_models": [],
        "photomaker": [],
        "model_patches": [],
        "audio_encoders": [],
        "background_removal": [],
        "frame_interpolation": [],
        "upscale_models": [],
        "diffusers": [],
        "gligen": [],
        "embeddings": [],
        "geometry_estimation": [],
        "optical_flow": [],
        "detection": [],
        "input": [],
        "input_3d": [],
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
            "text_encoders": "text_encoders",
            "clip_vision": "clip_vision",
            "style_models": "style_models",
            "diffusion_models": "diffusion_models",
            "photomaker": "photomaker",
            "model_patches": "model_patches",
            "audio_encoders": "audio_encoders",
            "background_removal": "background_removal",
            "frame_interpolation": "frame_interpolation",
            "upscale_models": "upscale_models",
            "diffusers": "diffusers",
            "gligen": "gligen",
            "embeddings": "embeddings",
            "geometry_estimation": "geometry_estimation",
            "optical_flow": "optical_flow",
            "detection": "detection",
        }

        for key, folder_name in path_mappings.items():
            try:
                folder_list = folder_paths.get_folder_paths(folder_name)
                paths[key] = [Path(p) for p in folder_list if p]
            except Exception:
                pass

        if not paths["text_encoders"] and paths["clip"]:
            paths["text_encoders"] = list(paths["clip"])

        # Input/output folders
        try:
            input_dir = Path(folder_paths.get_input_directory())
            paths["input"] = [input_dir]
            paths["input_3d"] = [input_dir / "3d"]
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

    candidate_names = _candidate_relative_names(filename, category)

    # Also search common parent directories
    for search_path in search_paths:
        if not search_path.exists():
            continue

        # Direct match
        for candidate_name in candidate_names:
            full_path = search_path / candidate_name
            if full_path.exists():
                return True, full_path

        # Check subdirectories (one level)
        try:
            for subdir in search_path.iterdir():
                if subdir.is_dir():
                    for candidate_name in candidate_names:
                        full_path = subdir / candidate_name
                        if full_path.exists():
                            return True, full_path
        except (PermissionError, OSError):
            continue

    return False, None


def _candidate_relative_names(filename: str, category: str) -> List[str]:
    """Return relative lookup candidates for host-specific asset categories."""
    candidates = [filename]

    if category == "input_3d":
        normalized = filename.replace("\\", "/")
        if normalized.startswith(INPUT_3D_PREFIX):
            candidates.append(normalized[len(INPUT_3D_PREFIX):])

    unique_candidates: List[str] = []
    seen: Set[str] = set()
    for candidate in candidates:
        if candidate and candidate not in seen:
            seen.add(candidate)
            unique_candidates.append(candidate)
    return unique_candidates


def _is_path_like(value: str) -> bool:
    """Heuristic to determine if a string looks like a file path."""
    if not isinstance(value, str) or len(value) < 3:
        return False

    # Check for common path patterns
    # Has extension that looks like a model or media file
    lower = value.lower()
    for ext in MODEL_EXTENSIONS | MEDIA_EXTENSIONS | THREE_D_EXTENSIONS:
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
            category = _determine_asset_category(node_type, value)
            if (
                value.strip().lower() in {"none", "null"}
                or (
                    not _is_path_like(value)
                    and category not in FOLDER_ASSET_CATEGORIES
                )
            ):
                continue

            checked_paths.add(value)

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
                if full_path and full_path.is_file():
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

    if "diffusers" in lower_type:
        return "diffusers"
    if "gligen" in lower_type:
        return "gligen"
    if "load3d" in lower_type or any(lower_file.endswith(ext) for ext in THREE_D_EXTENSIONS):
        return "input_3d"
    if "checkpoint" in lower_type:
        return "checkpoints"
    if "vae" in lower_type:
        return "vae"
    if "lora" in lower_type:
        return "loras"
    if "controlnet" in lower_type:
        return "controlnet"
    if "clipvision" in lower_type or "clip_vision" in lower_type or "clip-vision" in lower_type:
        return "clip_vision"
    if "stylemodel" in lower_type or "style_model" in lower_type or "style-model" in lower_type:
        return "style_models"
    if "unet" in lower_type or "diffusion" in lower_type:
        return "diffusion_models"
    if "photomaker" in lower_type:
        return "photomaker"
    if "backgroundremoval" in lower_type or "background_removal" in lower_type:
        return "background_removal"
    if "frameinterpolation" in lower_type or "frame_interpolation" in lower_type:
        return "frame_interpolation"
    if "opticalflow" in lower_type or "optical_flow" in lower_type:
        return "optical_flow"
    if "audioencoder" in lower_type or "audio_encoder" in lower_type:
        return "audio_encoders"
    if "modelpatch" in lower_type or "model_patch" in lower_type:
        return "model_patches"
    if "clip" in lower_type or "textencoder" in lower_type or "text_encoder" in lower_type:
        return "text_encoders"
    if "upscale" in lower_type:
        return "upscale_models"
    if "embed" in lower_type:
        return "embeddings"
    if (
        "moge" in lower_type
        or "geometry" in lower_type
        or "depth" in lower_type
        or "moge" in lower_file
        or "geometry" in lower_file
        or "depth_anything" in lower_file
        or "depth-anything" in lower_file
    ):
        return "geometry_estimation"
    if (
        "mediapipe" in lower_type
        or "detection" in lower_type
        or "landmarker" in lower_type
        or "blazeface" in lower_type
        or "mediapipe" in lower_file
        or "detector" in lower_file
        or "detection" in lower_file
        or "landmarker" in lower_file
        or "blazeface" in lower_file
    ):
        return "detection"
    if "loadimage" in lower_type or any(lower_file.endswith(ext) for ext in MEDIA_EXTENSIONS):
        return "input"
    if (
        "clip_vision" in lower_file
        or "clip-vision" in lower_file
        or "clipvision" in lower_file
    ):
        return "clip_vision"
    if "style_model" in lower_file or "style-model" in lower_file:
        return "style_models"
    if "photomaker" in lower_file:
        return "photomaker"
    if "birefnet" in lower_file or "background_removal" in lower_file:
        return "background_removal"
    if "frame_interpolation" in lower_file or "film" in lower_file:
        return "frame_interpolation"
    if "optical_flow" in lower_file or "raft" in lower_file:
        return "optical_flow"
    if "audio_encoder" in lower_file:
        return "audio_encoders"
    if "model_patch" in lower_file:
        return "model_patches"
    if (
        "wan2_2_high_noise" in lower_file
        or "wan2_2_low_noise" in lower_file
        or "diffusion" in lower_file
        or "unet" in lower_file
    ):
        return "diffusion_models"
    if (
        "clip_" in lower_file
        or "t5xxl" in lower_file
        or "text_encoder" in lower_file
        or "text-encoder" in lower_file
    ):
        return "text_encoders"
    if "ckpt" in lower_file:
        return "checkpoints"

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
