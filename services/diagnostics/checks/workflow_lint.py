"""
F14 Proactive Diagnostics - Workflow Lint Check

Analyzes workflow graph structure to detect:
1. Disconnected links / missing required inputs
2. Unsupported nodes / missing custom nodes
3. Obvious parameter anti-patterns (batch > threshold, resolution > threshold)
"""

import logging
from typing import Dict, Any, List, Set, Tuple

from ..models import (
    HealthIssue,
    HealthCheckRequest,
    IssueCategory,
    IssueSeverity,
    IssueTarget,
)
from . import register_check

logger = logging.getLogger("comfyui-doctor.diagnostics.checks.workflow_lint")


# ============================================================================
# Configuration
# ============================================================================

# Known core ComfyUI node types (not exhaustive, but covers common cases)
# This helps distinguish between "missing custom node" vs "typo in node type"
KNOWN_CORE_NODE_TYPES: Set[str] = {
    # Loaders
    "CheckpointLoaderSimple", "CheckpointLoader", "VAELoader", "CLIPLoader",
    "LoraLoader", "LoraLoaderModelOnly", "ControlNetLoader", "StyleModelLoader",
    "CLIPVisionLoader", "UpscaleModelLoader", "GLIGENLoader", "HypernetworkLoader",
    "LoadImage", "LoadImageMask", "LoadLatent",
    # Samplers
    "KSampler", "KSamplerAdvanced", "SamplerCustom",
    # Conditioning
    "CLIPTextEncode", "CLIPTextEncodeSDXL", "CLIPSetLastLayer",
    "ConditioningCombine", "ConditioningAverage", "ConditioningConcat",
    "ConditioningSetArea", "ConditioningSetAreaPercentage",
    "ConditioningSetMask", "ConditioningZeroOut",
    "ControlNetApply", "ControlNetApplyAdvanced",
    # Latent
    "EmptyLatentImage", "LatentUpscale", "LatentUpscaleBy", "LatentFromBatch",
    "RepeatLatentBatch", "LatentComposite", "LatentBlend", "LatentRotate",
    "LatentFlip", "LatentCrop", "SetLatentNoiseMask", "LatentCompositeMasked",
    # Image
    "VAEDecode", "VAEEncode", "VAEEncodeForInpaint", "VAEDecodeTiled",
    "VAEEncodeTiled", "ImageScale", "ImageScaleBy", "ImageUpscaleWithModel",
    "ImageSharpen", "ImageInvert", "ImagePadForOutpaint", "ImageBatch",
    "ImageCompositeMasked", "JoinImageWithAlpha", "SplitImageWithAlpha",
    "ImageBlend", "ImageBlur", "ImageQuantize", "ImageToMask",
    # Mask
    "MaskToImage", "ImageToMask", "SolidMask", "InvertMask", "CropMask",
    "MaskComposite", "FeatherMask", "GrowMask", "ThresholdMask",
    # Model
    "ModelSamplingDiscrete", "ModelSamplingContinuousEDM",
    "RescaleCFG", "FreeU", "FreeU_V2",
    # Utilities
    "PreviewImage", "SaveImage", "SaveLatent",
    "PrimitiveNode", "Reroute", "Note",
}

# Parameter thresholds for anti-pattern detection
PARAM_THRESHOLDS = {
    "batch_size": 16,       # batch > 16 is usually a mistake
    "width": 4096,          # resolution > 4096 is risky
    "height": 4096,
    "steps": 150,           # steps > 150 is usually overkill
    "cfg": 30,              # CFG > 30 is usually too high
}

# Widget names that typically contain these parameters
BATCH_WIDGETS = {"batch_size", "amount", "batch"}
RESOLUTION_WIDGETS = {"width", "height", "image_width", "image_height"}
STEPS_WIDGETS = {"steps", "step", "num_steps"}
CFG_WIDGETS = {"cfg", "cfg_scale", "guidance_scale"}


# ============================================================================
# Check Implementation
# ============================================================================

@register_check("workflow_lint")
async def check_workflow_lint(
    workflow: Dict[str, Any],
    request: HealthCheckRequest,
) -> List[HealthIssue]:
    """
    Lint workflow for structural issues and anti-patterns.

    Returns list of HealthIssues for detected problems.
    """
    issues: List[HealthIssue] = []

    nodes = workflow.get("nodes", [])
    links = workflow.get("links", [])

    if not isinstance(nodes, list):
        return issues

    # Build node lookup
    node_map: Dict[int, Dict[str, Any]] = {}
    for node in nodes:
        if isinstance(node, dict):
            node_id = node.get("id")
            if node_id is not None:
                node_map[int(node_id)] = node

    # Build link lookup: link_id -> (from_node, from_slot, to_node, to_slot)
    link_map: Dict[int, Tuple[int, int, int, int]] = {}
    if isinstance(links, list):
        for link in links:
            if isinstance(link, list) and len(link) >= 5:
                link_id, from_node, from_slot, to_node, to_slot = link[:5]
                link_map[link_id] = (from_node, from_slot, to_node, to_slot)

    # Check 1: Disconnected/broken links
    issues.extend(_check_disconnected_links(node_map, link_map))

    # Check 2: Missing/unsupported nodes
    issues.extend(_check_unsupported_nodes(node_map))

    # Check 3: Parameter anti-patterns
    issues.extend(_check_parameter_antipatterns(node_map))

    return issues


def _check_disconnected_links(
    node_map: Dict[int, Dict[str, Any]],
    link_map: Dict[int, Tuple[int, int, int, int]],
) -> List[HealthIssue]:
    """Check for disconnected or broken links."""
    issues: List[HealthIssue] = []

    # Check each node's inputs for broken links
    for node_id, node in node_map.items():
        node_type = node.get("type", "Unknown")
        node_title = node.get("title", node_type)

        # Check inputs array for None entries (disconnected required inputs)
        inputs = node.get("inputs", [])
        if isinstance(inputs, list):
            for idx, inp in enumerate(inputs):
                if isinstance(inp, dict):
                    input_name = inp.get("name", f"input_{idx}")
                    link_id = inp.get("link")

                    # link is null but input exists - might be optional
                    # Check if there's a type hint suggesting it's required
                    input_type = inp.get("type", "")

                    if link_id is None:
                        # Some inputs are optional (like CLIP in some loaders)
                        # We'll only warn for clearly required types
                        required_types = {"MODEL", "CLIP", "VAE", "LATENT", "CONDITIONING"}
                        if input_type in required_types:
                            target = IssueTarget(node_id=node_id)
                            issues.append(HealthIssue(
                                issue_id=HealthIssue.generate_issue_id(
                                    "disconnected_input",
                                    target,
                                    f"{input_name}:{input_type}",
                                ),
                                category=IssueCategory.WORKFLOW,
                                severity=IssueSeverity.WARNING,
                                title="Disconnected Required Input",
                                summary=f"Node '{node_title}' (#{node_id}) has unconnected input '{input_name}' of type {input_type}",
                                evidence=[
                                    f"Input '{input_name}' expects type '{input_type}'",
                                    f"Node type: {node_type}",
                                ],
                                recommendation=[
                                    f"Connect the '{input_name}' input to a compatible output",
                                    "Use 'Locate Node' to find this node on the canvas",
                                ],
                                target=target,
                            ))

                    elif link_id is not None and link_id not in link_map:
                        # Link ID exists but not in links array - broken reference
                        target = IssueTarget(node_id=node_id)
                        issues.append(HealthIssue(
                            issue_id=HealthIssue.generate_issue_id(
                                "broken_link",
                                target,
                                f"{input_name}:{link_id}",
                            ),
                            category=IssueCategory.WORKFLOW,
                            severity=IssueSeverity.CRITICAL,
                            title="Broken Link Reference",
                            summary=f"Node '{node_title}' (#{node_id}) has a broken link on input '{input_name}'",
                            evidence=[
                                f"Link ID {link_id} does not exist in workflow",
                                f"Input '{input_name}' cannot receive data",
                            ],
                            recommendation=[
                                "Reconnect the input to a valid output",
                                "This may have been caused by a copy/paste issue",
                            ],
                            target=target,
                        ))

    return issues


def _check_unsupported_nodes(
    node_map: Dict[int, Dict[str, Any]],
) -> List[HealthIssue]:
    """Check for potentially missing or unsupported nodes."""
    issues: List[HealthIssue] = []

    for node_id, node in node_map.items():
        node_type = node.get("type", "")
        if not node_type:
            continue

        # Skip known core nodes
        if node_type in KNOWN_CORE_NODE_TYPES:
            continue

        # Check for common custom node prefixes (these are expected to be custom)
        custom_prefixes = (
            "IPAdapter", "ControlNet", "AnimateDiff", "VHS_", "Impact",
            "Efficiency", "WAS_", "rgthree", "Derfuu", "ComfyMath",
            "KJNodes", "MTB_", "smZ", "CR_", "easy_", "Comfy_",
        )

        is_likely_custom = any(node_type.startswith(prefix) for prefix in custom_prefixes)

        # Check for error indicators in the node (ComfyUI marks missing nodes)
        # Note: This is heuristic - actual missing node detection requires backend
        widgets_values = node.get("widgets_values", [])
        properties = node.get("properties", {})

        # If node has "Node not found" style properties, it's definitely missing
        if properties.get("missing_node"):
            target = IssueTarget(node_id=node_id)
            issues.append(HealthIssue(
                issue_id=HealthIssue.generate_issue_id("missing_node", target, node_type),
                category=IssueCategory.DEPS,
                severity=IssueSeverity.CRITICAL,
                title="Missing Custom Node",
                summary=f"Custom node '{node_type}' (#{node_id}) is not installed",
                evidence=[
                    f"Node type: {node_type}",
                    "This node type is not recognized by ComfyUI",
                ],
                recommendation=[
                    f"Install the custom node pack containing '{node_type}'",
                    "Check ComfyUI Manager for available custom node packs",
                    "Restart ComfyUI after installing new nodes",
                ],
                target=target,
            ))
        elif not is_likely_custom and node_type not in KNOWN_CORE_NODE_TYPES:
            # Unknown node type - might be missing or typo
            # Only flag as INFO since we can't be certain
            target = IssueTarget(node_id=node_id)
            issues.append(HealthIssue(
                issue_id=HealthIssue.generate_issue_id("unknown_node", target, node_type),
                category=IssueCategory.WORKFLOW,
                severity=IssueSeverity.INFO,
                title="Unknown Node Type",
                summary=f"Node type '{node_type}' (#{node_id}) is not in the known node registry",
                evidence=[
                    f"Node type: {node_type}",
                    "This may be a custom node or a recently added core node",
                ],
                recommendation=[
                    "Verify this node works correctly in your ComfyUI installation",
                    "If this is a custom node, ensure it's properly installed",
                ],
                target=target,
            ))

    return issues


def _check_parameter_antipatterns(
    node_map: Dict[int, Dict[str, Any]],
) -> List[HealthIssue]:
    """Check for obvious parameter anti-patterns."""
    issues: List[HealthIssue] = []

    for node_id, node in node_map.items():
        node_type = node.get("type", "")
        node_title = node.get("title", node_type)
        widgets_values = node.get("widgets_values", [])

        if not isinstance(widgets_values, list):
            continue

        # Get widget names from inputs (if available) to map values
        inputs = node.get("inputs", [])
        outputs = node.get("outputs", [])

        # For KSampler and similar nodes, check common parameters
        if "KSampler" in node_type or "Sampler" in node_type:
            issues.extend(_check_sampler_params(node_id, node_title, node_type, widgets_values))

        # For EmptyLatentImage, check resolution
        if "EmptyLatentImage" in node_type or "LatentImage" in node_type:
            issues.extend(_check_latent_params(node_id, node_title, node_type, widgets_values))

        # Generic widget value checks
        issues.extend(_check_generic_widget_values(node_id, node_title, node_type, widgets_values))

    return issues


def _check_sampler_params(
    node_id: int,
    node_title: str,
    node_type: str,
    widgets_values: List[Any],
) -> List[HealthIssue]:
    """Check KSampler-type nodes for anti-patterns."""
    issues: List[HealthIssue] = []

    # KSampler widget order is typically:
    # seed, control_after_generate, steps, cfg, sampler_name, scheduler, denoise
    # But this can vary, so we check all numeric values

    for idx, value in enumerate(widgets_values):
        if not isinstance(value, (int, float)):
            continue

        # Check for extremely high steps
        if 20 <= value <= 1000:  # Likely steps value range
            if value > PARAM_THRESHOLDS["steps"]:
                target = IssueTarget(node_id=node_id)
                issues.append(HealthIssue(
                    issue_id=HealthIssue.generate_issue_id(
                        "high_steps", target, f"{value}"
                    ),
                    category=IssueCategory.PERFORMANCE,
                    severity=IssueSeverity.WARNING,
                    title="Very High Step Count",
                    summary=f"Node '{node_title}' (#{node_id}) has {int(value)} steps, which may be excessive",
                    evidence=[
                        f"Steps value: {int(value)}",
                        f"Threshold: {PARAM_THRESHOLDS['steps']}",
                        "High step counts significantly increase generation time",
                    ],
                    recommendation=[
                        f"Consider reducing steps to {PARAM_THRESHOLDS['steps']} or below",
                        "Most models converge well before 100 steps",
                    ],
                    target=target,
                ))
                break  # Only report once per node

        # Check for extremely high CFG
        if 1 <= value <= 50:  # Likely CFG value range
            if value > PARAM_THRESHOLDS["cfg"]:
                target = IssueTarget(node_id=node_id)
                issues.append(HealthIssue(
                    issue_id=HealthIssue.generate_issue_id(
                        "high_cfg", target, f"{value}"
                    ),
                    category=IssueCategory.WORKFLOW,
                    severity=IssueSeverity.INFO,
                    title="Very High CFG Value",
                    summary=f"Node '{node_title}' (#{node_id}) has CFG {value}, which may produce artifacts",
                    evidence=[
                        f"CFG value: {value}",
                        f"Recommended max: {PARAM_THRESHOLDS['cfg']}",
                    ],
                    recommendation=[
                        "High CFG values often cause oversaturation and artifacts",
                        "Try values between 5-15 for most use cases",
                    ],
                    target=target,
                ))
                break

    return issues


def _check_latent_params(
    node_id: int,
    node_title: str,
    node_type: str,
    widgets_values: List[Any],
) -> List[HealthIssue]:
    """Check latent image nodes for resolution anti-patterns."""
    issues: List[HealthIssue] = []

    # EmptyLatentImage widget order: width, height, batch_size
    width = None
    height = None
    batch_size = None

    for idx, value in enumerate(widgets_values):
        if not isinstance(value, (int, float)):
            continue

        value = int(value)

        # Detect based on typical value ranges
        if 64 <= value <= 8192:
            if width is None:
                width = value
            elif height is None:
                height = value
        elif 1 <= value <= 64:
            batch_size = value

    # Check for extreme resolutions
    if width and width > PARAM_THRESHOLDS["width"]:
        target = IssueTarget(node_id=node_id)
        issues.append(HealthIssue(
            issue_id=HealthIssue.generate_issue_id("high_width", target, f"{width}"),
            category=IssueCategory.PERFORMANCE,
            severity=IssueSeverity.WARNING,
            title="Very High Resolution Width",
            summary=f"Node '{node_title}' (#{node_id}) has width {width}px, which requires significant VRAM",
            evidence=[
                f"Width: {width}px",
                f"Threshold: {PARAM_THRESHOLDS['width']}px",
            ],
            recommendation=[
                "Consider using a lower resolution and upscaling afterwards",
                "High resolutions can cause VRAM issues or slow generation",
            ],
            target=target,
        ))

    if height and height > PARAM_THRESHOLDS["height"]:
        target = IssueTarget(node_id=node_id)
        issues.append(HealthIssue(
            issue_id=HealthIssue.generate_issue_id("high_height", target, f"{height}"),
            category=IssueCategory.PERFORMANCE,
            severity=IssueSeverity.WARNING,
            title="Very High Resolution Height",
            summary=f"Node '{node_title}' (#{node_id}) has height {height}px, which requires significant VRAM",
            evidence=[
                f"Height: {height}px",
                f"Threshold: {PARAM_THRESHOLDS['height']}px",
            ],
            recommendation=[
                "Consider using a lower resolution and upscaling afterwards",
                "High resolutions can cause VRAM issues or slow generation",
            ],
            target=target,
        ))

    # Check for high batch sizes
    if batch_size and batch_size > PARAM_THRESHOLDS["batch_size"]:
        target = IssueTarget(node_id=node_id)
        issues.append(HealthIssue(
            issue_id=HealthIssue.generate_issue_id("high_batch", target, f"{batch_size}"),
            category=IssueCategory.PERFORMANCE,
            severity=IssueSeverity.WARNING,
            title="Very High Batch Size",
            summary=f"Node '{node_title}' (#{node_id}) has batch size {batch_size}, which multiplies VRAM usage",
            evidence=[
                f"Batch size: {batch_size}",
                f"Threshold: {PARAM_THRESHOLDS['batch_size']}",
                "Each batch item requires additional VRAM",
            ],
            recommendation=[
                f"Consider reducing batch size to {PARAM_THRESHOLDS['batch_size']} or below",
                "Generate images sequentially if VRAM is limited",
            ],
            target=target,
        ))

    return issues


def _check_generic_widget_values(
    node_id: int,
    node_title: str,
    node_type: str,
    widgets_values: List[Any],
) -> List[HealthIssue]:
    """Check generic widget values for common anti-patterns."""
    issues: List[HealthIssue] = []

    # Check for suspiciously large numbers that might indicate mistakes
    for idx, value in enumerate(widgets_values):
        if isinstance(value, (int, float)) and value > 100000:
            # Very large number - might be an error (e.g., seed is fine, but others aren't)
            # Skip if it looks like a seed (very large int)
            if isinstance(value, int) and value > 1000000000:
                continue  # Likely a seed

            target = IssueTarget(node_id=node_id)
            issues.append(HealthIssue(
                issue_id=HealthIssue.generate_issue_id(
                    "suspicious_value", target, f"{idx}:{value}"
                ),
                category=IssueCategory.WORKFLOW,
                severity=IssueSeverity.INFO,
                title="Unusually Large Parameter Value",
                summary=f"Node '{node_title}' (#{node_id}) has an unusually large value: {value}",
                evidence=[
                    f"Widget index {idx} has value: {value}",
                    "This might be intentional or a typo",
                ],
                recommendation=[
                    "Verify this parameter value is intentional",
                ],
                target=target,
            ))

    return issues
