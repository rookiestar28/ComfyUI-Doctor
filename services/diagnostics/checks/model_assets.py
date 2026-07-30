"""
F14 Proactive Diagnostics - Model Assets Check

Analyzes workflow to detect:
1. File paths in widget values (models, images, etc.)
2. Validate existence and readability
"""

import logging
import os
import re
from dataclasses import dataclass
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
    ".safetensors", ".ckpt", ".pt", ".pt2", ".pth", ".bin", ".sft",
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

DATASET_WIDGET_CATEGORIES = {
    ("LoadImageDataSetFromFolder", "folder"): "input",
    ("LoadImageTextDataSetFromFolder", "folder"): "input",
    ("LoadVideoDataSetFromFolder", "folder"): "input",
    ("LoadVideoTextDataSetFromFolder", "folder"): "input",
    ("LoadTrainingDataset", "folder_name"): "datasets",
}

INPUT_3D_PREFIX = "3d/"
INVALID_ASSET_DISPLAY_NAME = "[invalid asset path]"
DEFAULT_MAX_PATHS = 50
MAX_PATH_BUDGET = 500
MAX_WORKFLOW_NODES = 1000
MAX_SUBGRAPH_DEPTH = 8
MAX_NAMED_WIDGET_ENTRIES = 256
MAX_NAMED_WIDGET_KEY_LENGTH = 128
MAX_NAMED_WIDGET_VALUE_LENGTH = 4096
RESERVED_NAMED_WIDGET_KEYS = frozenset({
    "__proto__",
    "constructor",
    "prototype",
})


# ============================================================================
# ComfyUI Folder Detection
# ============================================================================

_comfy_paths: Optional[Dict[str, List[Path]]] = None
_comfy_extensions: dict[str, set[str]] | None = None


@dataclass(frozen=True)
class _ContainedAssetPath:
    """A candidate resolved together with the authoritative root containing it."""

    root: Path
    candidate: Path


def _get_comfy_model_paths() -> Dict[str, List[Path]]:
    """Get a validated snapshot of ComfyUI's registered asset roots."""
    global _comfy_paths, _comfy_extensions
    if _comfy_paths is not None:
        return _comfy_paths

    fallback_paths: dict[str, list[Path]] = {
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
    paths = fallback_paths
    extensions: dict[str, set[str]] = {
        category: set(MODEL_EXTENSIONS)
        for category in fallback_paths
        if category not in {"input", "input_3d", "output"}
    }
    extensions["diffusers"] = {"folder"}
    extensions["input"] = set(MEDIA_EXTENSIONS)
    extensions["input_3d"] = set(THREE_D_EXTENSIONS)
    extensions["output"] = set(MEDIA_EXTENSIONS)

    try:
        import folder_paths

        registry = getattr(folder_paths, "folder_names_and_paths", None)
        if isinstance(registry, dict):
            # IMPORTANT: the live host registry is authoritative when present;
            # do not silently mix it with stale fixed model roots.
            paths = {}
            extensions = {}
            for category, entry in registry.items():
                if (
                    not isinstance(category, str)
                    or not isinstance(entry, (tuple, list))
                    or len(entry) < 2
                ):
                    continue
                raw_roots, raw_extensions = entry[0], entry[1]
                if (
                    isinstance(raw_roots, (str, bytes))
                    or not isinstance(raw_roots, (tuple, list, set))
                    or isinstance(raw_extensions, (str, bytes))
                    or not isinstance(
                        raw_extensions,
                        (tuple, list, set, frozenset),
                    )
                ):
                    continue

                valid_roots: list[Path] = []
                for raw_root in raw_roots:
                    try:
                        if raw_root and "\x00" not in os.fspath(raw_root):
                            valid_roots.append(Path(raw_root))
                    except (OSError, TypeError, ValueError):
                        continue

                valid_extensions: set[str] = set()
                for raw_extension in raw_extensions:
                    if not isinstance(raw_extension, str):
                        continue
                    extension = raw_extension.strip().lower()
                    if extension == "folder" or extension == "":
                        valid_extensions.add(extension)
                    elif extension.startswith("."):
                        valid_extensions.add(extension)

                paths[category] = valid_roots
                extensions[category] = valid_extensions
        else:
            path_mappings = {
                key: key
                for key in fallback_paths
                if key not in {"input", "input_3d", "output"}
            }
            for key, folder_name in path_mappings.items():
                try:
                    folder_list = folder_paths.get_folder_paths(folder_name)
                    paths[key] = [Path(p) for p in folder_list if p]
                except Exception:
                    pass

        if not paths.get("text_encoders") and paths.get("clip"):
            paths["text_encoders"] = list(paths["clip"])
            extensions["text_encoders"] = set(
                extensions.get("clip", MODEL_EXTENSIONS)
            )

        # Input/output folders
        try:
            input_dir = Path(folder_paths.get_input_directory())
            paths["input"] = [input_dir]
            paths["input_3d"] = [input_dir / "3d"]
            extensions["input"] = set(MEDIA_EXTENSIONS)
            extensions["input_3d"] = set(THREE_D_EXTENSIONS)
        except Exception:
            pass

        try:
            paths["output"] = [Path(folder_paths.get_output_directory())]
            extensions["output"] = set(MEDIA_EXTENSIONS)
        except Exception:
            pass

    except ImportError:
        logger.debug("folder_paths not available, using fallback detection")

    _comfy_paths = paths
    _comfy_extensions = extensions
    return paths


def _get_comfy_model_extensions() -> dict[str, set[str]]:
    """Return the cached host extension registry or deterministic fallback."""
    global _comfy_extensions
    if _comfy_extensions is None:
        _get_comfy_model_paths()
    if _comfy_extensions is not None:
        return _comfy_extensions
    return {
        "checkpoints": set(MODEL_EXTENSIONS),
        "input": set(MEDIA_EXTENSIONS),
        "input_3d": set(THREE_D_EXTENSIONS),
    }


def _clear_path_cache():
    """Clear path cache (for testing)."""
    global _comfy_paths, _comfy_extensions
    _comfy_paths = None
    _comfy_extensions = None


def _resolve_contained_asset_path(
    root: Path,
    candidate: str | Path,
) -> Optional[_ContainedAssetPath]:
    """Resolve a candidate only when its real path remains inside ``root``."""
    try:
        root_text = os.fspath(root)
        candidate_text = os.fspath(candidate)
        if "\x00" in root_text or "\x00" in candidate_text:
            return None
        normalized_candidate = candidate_text.replace("\\", "/")
        if ".." in normalized_candidate.split("/"):
            return None

        resolved_root_text = os.path.realpath(root_text)
        joined_candidate = os.path.join(root_text, candidate_text)
        resolved_candidate_text = os.path.realpath(joined_candidate)
        common = os.path.commonpath(
            (resolved_root_text, resolved_candidate_text)
        )

        # CRITICAL: no candidate existence/stat/open probe may move before
        # this realpath containment check; workflow widget paths are untrusted.
        if os.path.normcase(common) != os.path.normcase(resolved_root_text):
            return None

        return _ContainedAssetPath(
            root=Path(resolved_root_text),
            candidate=Path(resolved_candidate_text),
        )
    except (OSError, TypeError, ValueError):
        # Embedded nulls, Windows cross-drive paths, and resolution failures
        # are all invalid candidates and must fail closed.
        return None


def _find_file_in_comfy_paths(
    filename: str,
    category: str = "checkpoints",
) -> Tuple[bool, Optional[Path], Optional[Path], bool]:
    """
    Try to find a file in ComfyUI's model paths.

    Returns:
        ``(found, full_path, containing_root, invalid_candidate)``. A found
        path is always realpath-contained by the returned authoritative root.
    """
    paths = _get_comfy_model_paths()
    search_paths = paths.get(category, [])

    candidate_names = _candidate_relative_names(filename, category)
    candidate_was_contained = False
    has_forbidden_component = any(
        "\x00" in candidate_name
        or ".." in candidate_name.replace("\\", "/").split("/")
        for candidate_name in candidate_names
    )
    if has_forbidden_component:
        return False, None, None, True

    # Also search common parent directories
    for search_path in search_paths:
        # Direct match
        for candidate_name in candidate_names:
            contained = _resolve_contained_asset_path(
                search_path,
                candidate_name,
            )
            candidate_was_contained = (
                candidate_was_contained or contained is not None
            )
            if contained is not None and contained.candidate.exists():
                return True, contained.candidate, contained.root, False

        # Check subdirectories (one level)
        try:
            contained_root = _resolve_contained_asset_path(search_path, ".")
            if contained_root is None:
                continue

            for subdir in contained_root.candidate.iterdir():
                contained_subdir = _resolve_contained_asset_path(
                    contained_root.root,
                    subdir,
                )
                if (
                    contained_subdir is not None
                    and contained_subdir.candidate.is_dir()
                ):
                    for candidate_name in candidate_names:
                        contained = _resolve_contained_asset_path(
                            contained_root.root,
                            contained_subdir.candidate / candidate_name,
                        )
                        if (
                            contained is not None
                            and contained.candidate.exists()
                        ):
                            return (
                                True,
                                contained.candidate,
                                contained.root,
                                False,
                            )
        except (PermissionError, OSError):
            continue

    try:
        is_absolute = Path(filename).is_absolute()
    except (OSError, ValueError):
        is_absolute = True

    invalid_candidate = (
        is_absolute or (bool(search_paths) and not candidate_was_contained)
    )
    return False, None, None, invalid_candidate


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
    registered_extensions = {
        extension
        for values in _get_comfy_model_extensions().values()
        for extension in values
        if extension and extension != "folder"
    }
    for ext in (
        MEDIA_EXTENSIONS
        | THREE_D_EXTENSIONS
        | registered_extensions
    ):
        if lower.endswith(ext):
            return True

    # Contains path separators
    if "/" in value or "\\" in value:
        return True

    # Ends with common model naming patterns
    if re.search(r"[-_]v?\d+(\.\d+)?$", value):
        return True

    return False


def _is_folder_asset_category(category: str) -> bool:
    """Return whether a host registry category contains folder assets."""
    return (
        category in FOLDER_ASSET_CATEGORIES
        or "folder" in _get_comfy_model_extensions().get(category, set())
    )


def _dataset_widget_category(
    node_type: str,
    node: dict[str, Any],
    widget_index: int,
) -> str | None:
    """Return the authoritative root category for an exact dataset widget."""
    widget_names = _node_widget_names(node)
    if widget_index < 0 or widget_index >= len(widget_names):
        return None
    widget_name = widget_names[widget_index]
    if widget_name is None:
        return None
    return DATASET_WIDGET_CATEGORIES.get((node_type, widget_name))


def _find_dataset_folder(
    folder_name: str,
    category: str,
) -> tuple[bool, bool, _ContainedAssetPath | None, bool]:
    """Find one exact contained dataset directory without enumerating it."""
    roots = _get_comfy_model_paths().get(category, [])
    if not roots:
        return False, False, None, False

    normalized = folder_name.replace("\\", "/")
    if (
        len(folder_name) > MAX_NAMED_WIDGET_VALUE_LENGTH
        or "\x00" in folder_name
        or ".." in normalized.split("/")
    ):
        return True, False, None, True

    candidate_was_contained = False
    for root in roots:
        contained = _resolve_contained_asset_path(root, folder_name)
        if contained is None:
            continue
        if os.path.normcase(os.fspath(contained.candidate)) == os.path.normcase(
            os.fspath(contained.root)
        ):
            continue
        candidate_was_contained = True
        # CRITICAL: this directory probe must remain after realpath containment;
        # dataset widget values are untrusted and never authorize enumeration.
        if contained.candidate.is_dir():
            return True, True, contained, False

    try:
        is_absolute = Path(folder_name).is_absolute()
    except (OSError, ValueError):
        is_absolute = True
    return (
        True,
        False,
        None,
        is_absolute or not candidate_was_contained,
    )


def _dataset_folder_issue(
    context: "_WorkflowAssetNode",
    node_type: str,
    widget_index: int,
    folder_name: str,
    category: str,
    *,
    invalid_candidate: bool = False,
    unreadable: bool = False,
) -> HealthIssue:
    """Build a bounded dataset-folder finding without exposing private roots."""
    node_id = context.visible_node_id
    node_title = context.visible_node_title
    safe_name = (
        INVALID_ASSET_DISPLAY_NAME
        if invalid_candidate
        else _sanitize_path_for_display(folder_name)
    )
    problem = "not readable" if unreadable else "not found"
    title = (
        "Dataset Folder Not Readable"
        if unreadable
        else "Dataset Folder Not Found"
    )
    return HealthIssue(
        issue_id=HealthIssue.generate_issue_id(
            "dataset_folder_access" if unreadable else "missing_dataset_folder",
            IssueTarget(node_id=node_id),
            f"{folder_name[:32]}:{context.source_execution_id}",
        ),
        category=IssueCategory.MODEL,
        severity=IssueSeverity.WARNING,
        title=title,
        summary=(
            f"Node '{node_title}' (#{node_id}) references dataset folder "
            f"'{safe_name}' which is {problem}"
        ),
        evidence=[
            f"Folder: {safe_name}",
            f"Node type: {node_type}",
            f"Searched in: {category} folders",
        ],
        recommendation=[
            f"Ensure dataset folder '{safe_name}' exists in the configured "
            f"ComfyUI {category} root",
            "Check whether the folder was moved, renamed, or removed",
            "Verify that ComfyUI can read and enter the folder",
        ],
        target=IssueTarget(node_id=node_id),
        metadata=_asset_provenance_metadata(
            context,
            node_type,
            widget_index,
        ),
    )


def _registered_asset_category(
    node_type: str,
    filename: str,
) -> str | None:
    """Resolve a custom host category only from deterministic public facts."""
    paths = _get_comfy_model_paths()
    extensions = _get_comfy_model_extensions()
    normalized_type = re.sub(r"[^a-z0-9]", "", node_type.lower())

    name_matches: list[str] = []
    for category in paths:
        category_token = re.sub(r"[^a-z0-9]", "", category.lower())
        singular_token = (
            category_token[:-1]
            if category_token.endswith("s")
            else category_token
        )
        if (
            singular_token
            and singular_token in normalized_type
            and extensions.get(category)
        ):
            name_matches.append(category)
    if len(name_matches) == 1:
        return name_matches[0]

    try:
        suffix = Path(filename).suffix.lower()
    except (OSError, TypeError, ValueError):
        suffix = ""
    extension_matches = [
        category
        for category, registered in extensions.items()
        if suffix and suffix in registered and paths.get(category)
    ]
    if len(extension_matches) == 1:
        return extension_matches[0]
    return None


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


@dataclass(frozen=True)
class _WorkflowAssetNode:
    """An instantiated workflow node with visible/source provenance."""

    source_node: dict[str, Any]
    widget_values: tuple[Any, ...]
    visible_node_id: Any
    visible_node_title: str
    source_execution_id: str
    promoted_widget_indexes: frozenset[int]
    nested: bool


def _normalize_path_budget(value: Any) -> int:
    """Normalize the request path budget without allowing an unbounded scan."""
    if value is None:
        return DEFAULT_MAX_PATHS
    try:
        normalized = int(value)
    except (TypeError, ValueError, OverflowError):
        return DEFAULT_MAX_PATHS
    return max(0, min(MAX_PATH_BUDGET, normalized))


def _safe_execution_id_component(value: Any) -> str:
    """Keep provenance identifiers content-free and bounded."""
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_-]{1,64}", value):
        return value
    return "unknown"


def _widget_index_for_input(
    node: dict[str, Any],
    input_index: Any,
) -> int | None:
    """Map a serialized input slot to its widgets_values position."""
    if not isinstance(input_index, int) or input_index < 0:
        return None
    inputs = node.get("inputs", [])
    if not isinstance(inputs, list) or input_index >= len(inputs):
        return None

    widget_index = 0
    for current_index, input_slot in enumerate(inputs):
        if not isinstance(input_slot, dict):
            continue
        widget = input_slot.get("widget")
        if not isinstance(widget, dict) or not isinstance(
            widget.get("name"),
            str,
        ):
            continue
        if current_index == input_index:
            return widget_index
        widget_index += 1
    return None


def _safe_named_widget_values(node: dict[str, Any]) -> dict[str, str]:
    """Return a bounded node-local named widget map with supported values."""
    raw_values = node.get("widgets_values_named")
    if (
        not isinstance(raw_values, dict)
        or len(raw_values) > MAX_NAMED_WIDGET_ENTRIES
    ):
        return {}

    safe_values: dict[str, str] = {}
    for key, value in raw_values.items():
        if (
            not isinstance(key, str)
            or not key
            or len(key) > MAX_NAMED_WIDGET_KEY_LENGTH
            or key.casefold() in RESERVED_NAMED_WIDGET_KEYS
            or "\x00" in key
            or not isinstance(value, str)
            or len(value) > MAX_NAMED_WIDGET_VALUE_LENGTH
        ):
            continue
        safe_values[key] = value
    return safe_values


def _node_widget_names(node: dict[str, Any]) -> tuple[str | None, ...]:
    """Return widget names in their serialized positional order."""
    inputs = node.get("inputs", [])
    if (
        not isinstance(inputs, list)
        or len(inputs) > MAX_NAMED_WIDGET_ENTRIES
    ):
        return ()

    names: list[str | None] = []
    for input_slot in inputs:
        if not isinstance(input_slot, dict):
            continue
        widget = input_slot.get("widget")
        if not isinstance(widget, dict):
            continue
        name = widget.get("name")
        if (
            isinstance(name, str)
            and name
            and len(name) <= MAX_NAMED_WIDGET_KEY_LENGTH
            and name.casefold() not in RESERVED_NAMED_WIDGET_KEYS
            and "\x00" not in name
        ):
            names.append(name)
        else:
            # Preserve the positional slot so malformed schema cannot shift a
            # later named fallback onto the wrong serialized widget.
            names.append(None)
    return tuple(names)


def _effective_widget_values(node: dict[str, Any]) -> tuple[Any, ...]:
    """Resolve one positional-first value per schema-linked widget."""
    raw_positional = node.get("widgets_values", [])
    values = list(raw_positional) if isinstance(raw_positional, list) else []
    named_values = _safe_named_widget_values(node)
    if not named_values:
        return tuple(values)

    widget_names = _node_widget_names(node)
    widget_name_counts: dict[str, int] = {}
    for widget_name in widget_names:
        if widget_name is None:
            continue
        widget_name_counts[widget_name] = (
            widget_name_counts.get(widget_name, 0) + 1
        )
    for widget_index, widget_name in enumerate(widget_names):
        if widget_name is None:
            continue
        if widget_name_counts[widget_name] != 1:
            continue
        named_value = named_values.get(widget_name)
        if named_value is None:
            continue
        while len(values) <= widget_index:
            values.append(None)
        # IMPORTANT: current positional serialization stays authoritative;
        # named workflow data is untrusted fallback-only input.
        if values[widget_index] is None:
            values[widget_index] = named_value

    if (
        not widget_names
        and ("inputs" not in node or node.get("inputs") == [])
        and not any(isinstance(value, str) for value in values)
    ):
        # Older/minimal nodes may omit input schema. Restrict fallback to the
        # established path-widget allow-list instead of trusting arbitrary keys.
        values.extend(
            named_value
            for widget_name, named_value in named_values.items()
            if widget_name in PATH_WIDGET_NAMES
        )

    return tuple(values)


def _apply_promoted_widget_values(
    definition: dict[str, Any],
    host_node: dict[str, Any],
) -> list[tuple[dict[str, Any], frozenset[int]]]:
    """Apply host-owned promoted values to direct definition children."""
    raw_nodes = definition.get("nodes", [])
    if not isinstance(raw_nodes, list):
        return []

    effective: dict[Any, tuple[dict[str, Any], list[Any], set[int]]] = {}
    ordered_ids: list[Any] = []
    for node in raw_nodes:
        if not isinstance(node, dict):
            continue
        node_id = node.get("id")
        values = node.get("widgets_values", [])
        copied_values = list(values) if isinstance(values, list) else []
        effective[node_id] = (node, copied_values, set())
        ordered_ids.append(node_id)

    raw_inputs = definition.get("inputs", [])
    raw_links = definition.get("links", [])
    if not isinstance(raw_inputs, list) or not isinstance(raw_links, list):
        raw_inputs = []
        raw_links = []

    raw_host_values = host_node.get("widgets_values", [])
    host_values = (
        tuple(raw_host_values)
        if isinstance(raw_host_values, list)
        else ()
    )
    host_named_values = _safe_named_widget_values(host_node)
    host_widget_index = 0
    input_node = definition.get("inputNode", {})
    input_node_id = (
        input_node.get("id", -10)
        if isinstance(input_node, dict)
        else -10
    )
    for definition_input_index, definition_input in enumerate(raw_inputs):
        if not isinstance(definition_input, dict):
            continue
        link_ids = definition_input.get("linkIds", [])
        if not isinstance(link_ids, list):
            link_ids = []
        matching_links = [
            link
            for link in raw_links
            if isinstance(link, dict)
            and (
                link.get("id") in link_ids
                or (
                    link.get("origin_slot") == definition_input_index
                    and link.get("origin_id") in {
                        input_node_id,
                        str(input_node_id),
                    }
                )
            )
        ]

        widget_targets: list[tuple[Any, int]] = []
        for link in matching_links:
            target_id = link.get("target_id")
            target = effective.get(target_id)
            if target is None:
                continue
            widget_index = _widget_index_for_input(
                target[0],
                link.get("target_slot"),
            )
            if widget_index is not None:
                widget_targets.append((target_id, widget_index))

        if not widget_targets:
            continue
        has_positional_value = (
            host_widget_index < len(host_values)
            and host_values[host_widget_index] is not None
        )
        definition_input_name = definition_input.get("name")
        named_host_value = (
            host_named_values.get(definition_input_name)
            if isinstance(definition_input_name, str)
            else None
        )
        host_value = (
            host_values[host_widget_index]
            if has_positional_value
            else named_host_value
        )
        host_widget_index += 1
        if host_value is None:
            continue
        for target_id, widget_index in widget_targets:
            _source_node, values, promoted_indexes = effective[target_id]
            while len(values) <= widget_index:
                values.append(None)
            values[widget_index] = host_value
            promoted_indexes.add(widget_index)

    return [
        (
            effective[node_id][0]
            | {"widgets_values": effective[node_id][1]},
            frozenset(effective[node_id][2]),
        )
        for node_id in ordered_ids
    ]


def _collect_workflow_asset_nodes(
    workflow: dict[str, Any],
) -> list[_WorkflowAssetNode]:
    """Instantiate bounded root/subgraph nodes for model asset scanning."""
    raw_nodes = workflow.get("nodes", [])
    if not isinstance(raw_nodes, list):
        return []

    raw_definitions = workflow.get("definitions", {})
    raw_subgraphs = (
        raw_definitions.get("subgraphs", [])
        if isinstance(raw_definitions, dict)
        else []
    )
    if not isinstance(raw_subgraphs, list):
        raw_subgraphs = []
    definitions = {
        definition.get("id"): definition
        for definition in raw_subgraphs
        if isinstance(definition, dict)
        and isinstance(definition.get("id"), str)
    }

    contexts: list[_WorkflowAssetNode] = []
    visited_nodes = 0

    def visit(
        node: dict[str, Any],
        *,
        visible_node_id: Any,
        visible_node_title: str,
        source_prefix: str,
        promoted_indexes: frozenset[int],
        definition_stack: frozenset[str],
        depth: int,
        nested: bool,
    ) -> None:
        nonlocal visited_nodes
        if visited_nodes >= MAX_WORKFLOW_NODES:
            return
        visited_nodes += 1

        node_id = node.get("id")
        node_component = _safe_execution_id_component(node_id)
        source_execution_id = (
            f"{source_prefix}:{node_component}"
            if source_prefix
            else node_component
        )
        node_type = node.get("type", "")
        definition = definitions.get(node_type)
        if (
            isinstance(node_type, str)
            and isinstance(definition, dict)
            and node_type not in definition_stack
            and depth < MAX_SUBGRAPH_DEPTH
        ):
            children = _apply_promoted_widget_values(
                definition,
                node,
            )
            next_stack = definition_stack | {node_type}
            for child, child_promoted_indexes in children:
                visit(
                    child,
                    visible_node_id=visible_node_id,
                    visible_node_title=visible_node_title,
                    source_prefix=source_execution_id,
                    promoted_indexes=child_promoted_indexes,
                    definition_stack=next_stack,
                    depth=depth + 1,
                    nested=True,
                )
            return

        contexts.append(_WorkflowAssetNode(
            source_node=node,
            widget_values=_effective_widget_values(node),
            visible_node_id=visible_node_id,
            visible_node_title=visible_node_title,
            source_execution_id=source_execution_id,
            promoted_widget_indexes=promoted_indexes,
            nested=nested,
        ))

    for root_node in raw_nodes:
        if visited_nodes >= MAX_WORKFLOW_NODES:
            break
        if not isinstance(root_node, dict):
            continue
        root_id = root_node.get("id")
        root_type = root_node.get("type", "")
        root_title = root_node.get("title", root_type)
        visit(
            root_node,
            visible_node_id=root_id,
            visible_node_title=(
                root_title if isinstance(root_title, str) else str(root_type)
            ),
            source_prefix="",
            promoted_indexes=frozenset(),
            definition_stack=frozenset(),
            depth=0,
            nested=False,
        )

    return contexts


def _asset_provenance_metadata(
    context: _WorkflowAssetNode,
    source_node_type: str,
    widget_index: int,
) -> dict[str, Any]:
    """Build public-safe instance provenance for a nested asset finding."""
    if not context.nested:
        return {}
    source_node_id = context.source_node.get("id")
    safe_source_node_id: Any = (
        source_node_id
        if isinstance(source_node_id, int)
        else _safe_execution_id_component(source_node_id)
    )
    visible_node_id = context.visible_node_id
    safe_visible_node_id: Any = (
        visible_node_id
        if isinstance(visible_node_id, int)
        else _safe_execution_id_component(visible_node_id)
    )
    return {
        "asset_provenance": {
            "visible_node_id": safe_visible_node_id,
            "source_execution_id": context.source_execution_id,
            "source_node_id": safe_source_node_id,
            "source_node_type": source_node_type[:128],
            "promoted": widget_index in context.promoted_widget_indexes,
        }
    }


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
    node_contexts = _collect_workflow_asset_nodes(workflow)
    path_budget = _normalize_path_budget(request.max_paths)
    scanned_paths = 0

    # Track checked paths to avoid duplicates
    checked_paths: set[tuple[str, Any, str, int]] = set()

    for context in node_contexts:
        node = context.source_node
        node_id = context.visible_node_id
        node_type = node.get("type", "")
        if not isinstance(node_type, str):
            node_type = ""
        node_title = context.visible_node_title
        widgets_values = context.widget_values

        # Determine if this node type is known to load files
        is_file_loader = any(
            loader in node_type for loader in FILE_LOADING_NODE_TYPES
        )

        # Check each widget value
        for idx, value in enumerate(widgets_values):
            if not isinstance(value, str):
                continue

            checked_key = (
                value,
                context.visible_node_id,
                context.source_execution_id,
                idx,
            )
            if checked_key in checked_paths:
                continue

            # Determine if this looks like a file path.
            dataset_category = _dataset_widget_category(
                node_type,
                node,
                idx,
            )
            category = (
                dataset_category
                or _determine_asset_category(node_type, value)
            )
            if (
                value.strip().lower() in {"none", "null"}
                or (
                    not _is_path_like(value)
                    and not _is_folder_asset_category(category)
                    and dataset_category is None
                )
            ):
                continue

            if (
                dataset_category is not None
                and not _get_comfy_model_paths().get(dataset_category)
            ):
                # Older hosts without the authoritative category fail open;
                # never substitute checkpoints or another filesystem root.
                continue

            if scanned_paths >= path_budget:
                return issues
            scanned_paths += 1
            checked_paths.add(checked_key)

            if dataset_category is not None:
                (
                    category_available,
                    found,
                    contained_folder,
                    invalid_candidate,
                ) = _find_dataset_folder(value, dataset_category)
                if not category_available:
                    continue
                if not found or contained_folder is None:
                    issues.append(_dataset_folder_issue(
                        context,
                        node_type,
                        idx,
                        value,
                        dataset_category,
                        invalid_candidate=invalid_candidate,
                    ))
                    continue

                final_folder = _resolve_contained_asset_path(
                    contained_folder.root,
                    contained_folder.candidate,
                )
                if final_folder is None:
                    issues.append(_dataset_folder_issue(
                        context,
                        node_type,
                        idx,
                        value,
                        dataset_category,
                        invalid_candidate=True,
                    ))
                elif not os.access(
                    final_folder.candidate,
                    os.R_OK | os.X_OK,
                ):
                    issues.append(_dataset_folder_issue(
                        context,
                        node_type,
                        idx,
                        value,
                        dataset_category,
                        unreadable=True,
                    ))
                continue

            # Try to find the file
            (
                found,
                full_path,
                containing_root,
                invalid_candidate,
            ) = _find_file_in_comfy_paths(value, category)

            if found and full_path is not None and containing_root is not None:
                final_candidate = _resolve_contained_asset_path(
                    containing_root,
                    full_path,
                )
                if final_candidate is None:
                    found = False
                    full_path = None
                    containing_root = None
                    invalid_candidate = True
                else:
                    full_path = final_candidate.candidate
                    containing_root = final_candidate.root

            if not found:
                # File not found - report issue
                target = IssueTarget(node_id=node_id)

                # Severity depends on whether this is a known file loader
                severity = IssueSeverity.WARNING if is_file_loader else IssueSeverity.INFO

                safe_name = (
                    INVALID_ASSET_DISPLAY_NAME
                    if invalid_candidate
                    else _sanitize_path_for_display(value)
                )

                issues.append(HealthIssue(
                    issue_id=HealthIssue.generate_issue_id(
                        "missing_asset",
                        target,
                        f"{value[:32]}:{context.source_execution_id}",
                    ),
                    category=IssueCategory.MODEL,
                    severity=severity,
                    title="Asset File Not Found",
                    summary=f"Node '{node_title}' (#{node_id}) references file '{safe_name}' which cannot be found",
                    evidence=[
                        f"Filename: {safe_name}",
                        f"Node type: {node_type}",
                        f"Searched in: {category} folders",
                        *(
                            [
                                "Nested source execution ID: "
                                f"{context.source_execution_id}",
                            ]
                            if context.nested
                            else []
                        ),
                    ],
                    recommendation=[
                        f"Ensure the file '{safe_name}' exists in a configured or registered ComfyUI model folder",
                        "Check if the file was moved, renamed, or deleted",
                        "Verify the file name spelling (case-sensitive on some systems)",
                    ],
                    target=target,
                    metadata=_asset_provenance_metadata(
                        context,
                        node_type,
                        idx,
                    ),
                ))
            else:
                # File found - check if readable
                if (
                    full_path is not None
                    and containing_root is not None
                    and full_path.is_file()
                ):
                    readable_issue = _check_file_readable(
                        full_path,
                        containing_root,
                        node_id,
                        node_title,
                        node_type,
                        value,
                    )
                    if readable_issue:
                        readable_issue.metadata = _asset_provenance_metadata(
                            context,
                            node_type,
                            idx,
                        )
                        issues.append(readable_issue)

    return issues


def _determine_asset_category(node_type: str, filename: str) -> str:
    """Determine the asset category based on node type and filename."""
    if not isinstance(node_type, str):
        node_type = ""
    if not isinstance(filename, str):
        filename = ""
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

    # Preserve known loader hints, then consult validated custom registry
    # facts without guessing across ambiguous shared model extensions.
    return (
        _registered_asset_category(node_type, filename)
        or "checkpoints"
    )


def _check_file_readable(
    path: Path,
    containing_root: Path,
    node_id: int,
    node_title: str,
    node_type: str,
    original_value: str,
) -> Optional[HealthIssue]:
    """Check if a file is readable."""
    try:
        # IMPORTANT: re-resolve immediately before reading so a symlink change
        # cannot bypass the registered-root decision made during lookup.
        contained = _resolve_contained_asset_path(containing_root, path)
        if contained is None:
            raise OSError("asset path left its registered root")

        with open(contained.candidate, "rb") as f:
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
