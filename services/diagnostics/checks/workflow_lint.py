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
from ..known_nodes import STATIC_KNOWN_CORE_NODE_TYPES, is_known_node_type
from ..node_identity import (
    NodeIdentity,
    resolve_node_identities,
    safe_execution_id_component,
    valid_node_id,
    with_discriminator,
)

logger = logging.getLogger("comfyui-doctor.diagnostics.checks.workflow_lint")


# ============================================================================
# Configuration
# ============================================================================

# Known core node types now live in known_nodes.py; the name stays exported for existing callers.
KNOWN_CORE_NODE_TYPES: Set[str] = set(STATIC_KNOWN_CORE_NODE_TYPES)

OPTIONAL_SWITCH_INPUTS: frozenset[tuple[str, str]] = frozenset({
    ("ComfySwitchNode", "on_false"),
    ("ComfySwitchNode", "on_true"),
    ("ComfySoftSwitchNode", "on_false"),
    ("ComfySoftSwitchNode", "on_true"),
})

OPTIONAL_BRANCH_INPUTS: frozenset[str] = frozenset(
    f"autogrow.branch{index}" for index in range(32)
)

# Serialized form of `RenderShape.HollowCircle`. The host frontend writes it as `shape` on every input
# slot whose spec is optional (litegraphService.ts: `shape: inputSpec.isOptional ? ... : undefined`);
# it is present on the Desktop, core-pinned and standalone frontend lanes this project supports.
HOST_OPTIONAL_SLOT_SHAPE: int = 7


def _is_host_optional_slot(slot: Any) -> bool:
    """Return True only when the host serialized ``slot`` as optional (``shape`` exactly integer 7)."""
    # ``type(...) is int`` is deliberate: JSON producers can emit "7", 7.0 or booleans, and none of those
    # is the host's marker; accepting them would let a loosely typed producer widen the exemption.
    return (
        isinstance(slot, dict)
        and type(slot.get("shape")) is int
        and slot["shape"] == HOST_OPTIONAL_SLOT_SHAPE
    )

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

    # IMPORTANT: int(id) both crashes on opaque IDs and aliases "09" to 9, and a malformed or duplicate
    # id must never select a node. Every node is still linted: a node whose identity is not usable keeps
    # its findings but gets no node target (so Locate/fix cannot land on another node) and a position
    # discriminator in its issue ids (so two such nodes with identical findings stay distinct).
    identities = resolve_node_identities(nodes)

    # Build link lookup: link_id -> (from_node, from_slot, to_node, to_slot)
    link_map: Dict[int, Tuple[int, int, int, int]] = {}
    if isinstance(links, list):
        for link in links:
            if isinstance(link, list) and len(link) >= 5:
                link_id, from_node, from_slot, to_node, to_slot = link[:5]
                link_map[link_id] = (from_node, from_slot, to_node, to_slot)

    # Check 1: Disconnected/broken links
    issues.extend(_check_disconnected_links(identities, link_map))

    # Check 2: Missing/unsupported nodes
    issues.extend(_check_unsupported_nodes(identities))

    # Check 3: Parameter anti-patterns
    issues.extend(_check_parameter_antipatterns(identities))

    # Check 4: Duplicate node identities (reported once per group, never targeted at a node)
    issues.extend(_check_duplicate_identities(identities))

    return issues


LOCATE_NODE_STEP = "Use 'Locate Node' to find this node on the canvas"
NO_USABLE_ID_STEP = (
    "This node has no usable ID, so Locate Node is unavailable; "
    "save the workflow again so each node has a unique ID."
)
MAX_DUPLICATE_GROUPS = 20
MAX_DUPLICATE_POSITIONS = 8


def _check_disconnected_links(
    identities: List[NodeIdentity],
    link_map: Dict[int, Tuple[int, int, int, int]],
) -> List[HealthIssue]:
    """Check for disconnected or broken links."""
    issues: List[HealthIssue] = []

    # Check each node's inputs for broken links
    for identity in identities:
        node = identity.node
        node_id = identity.node_id
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
                        # IMPORTANT: MatchType propagates a type to optional Switch/Branch
                        # inputs. Type-only classification falsely requires these inputs;
                        # keep this exception inside the null-link branch so broken links warn.
                        if (
                            isinstance(node_type, str)
                            and isinstance(input_name, str)
                            and (
                                (node_type, input_name) in OPTIONAL_SWITCH_INPUTS
                                or (node_type == "BranchNode" and input_name in OPTIONAL_BRANCH_INPUTS)
                            )
                        ):
                            continue
                        # IMPORTANT: the host's own optional marker (`shape: 7`) is the authority for
                        # optionality, not the slot type or the node name: typed optional inputs such as
                        # VAE/CLIP on new first-party nodes would otherwise warn as "required". Keep this
                        # inside the null-link branch; moving it above would hide "Broken Link Reference"
                        # for an optional slot whose link id dangles. Do not widen it to other `shape`
                        # values or loosely typed 7 ("7", 7.0, True): those are different host states.
                        if _is_host_optional_slot(inp):
                            continue
                        # Some inputs are optional (like CLIP in some loaders)
                        # We'll only warn for clearly required types
                        required_types = {"MODEL", "CLIP", "VAE", "LATENT", "CONDITIONING"}
                        if input_type in required_types:
                            target = IssueTarget(node_id=node_id)
                            issues.append(HealthIssue(
                                issue_id=HealthIssue.generate_issue_id(
                                    "disconnected_input",
                                    target,
                                    with_discriminator(f"{input_name}:{input_type}", identity),
                                ),
                                category=IssueCategory.WORKFLOW,
                                severity=IssueSeverity.WARNING,
                                title="Disconnected Required Input",
                                summary=f"Node '{node_title}' ({identity.label}) has unconnected input '{input_name}' of type {input_type}",
                                evidence=[
                                    f"Input '{input_name}' expects type '{input_type}'",
                                    f"Node type: {node_type}",
                                ],
                                recommendation=[
                                    f"Connect the '{input_name}' input to a compatible output",
                                    LOCATE_NODE_STEP if identity.actionable else NO_USABLE_ID_STEP,
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
                                with_discriminator(f"{input_name}:{link_id}", identity),
                            ),
                            category=IssueCategory.WORKFLOW,
                            severity=IssueSeverity.CRITICAL,
                            title="Broken Link Reference",
                            summary=f"Node '{node_title}' ({identity.label}) has a broken link on input '{input_name}'",
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
    identities: List[NodeIdentity],
) -> List[HealthIssue]:
    """Check for potentially missing or unsupported nodes."""
    issues: List[HealthIssue] = []

    for identity in identities:
        node = identity.node
        node_id = identity.node_id
        node_type = node.get("type", "")
        # A type that is not a non-empty string is not a node name (and is unhashable when it is a list).
        if not isinstance(node_type, str) or not node_type:
            continue

        # Skip node types the running host registers (or the fallback list knows)
        if is_known_node_type(node_type):
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
                issue_id=HealthIssue.generate_issue_id(
                    "missing_node", target, with_discriminator(node_type, identity)
                ),
                category=IssueCategory.DEPS,
                severity=IssueSeverity.CRITICAL,
                title="Missing Custom Node",
                summary=f"Custom node '{node_type}' ({identity.label}) is not installed",
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
        elif not is_likely_custom:
            # Unknown node type - might be missing or typo
            # Only flag as INFO since we can't be certain
            target = IssueTarget(node_id=node_id)
            issues.append(HealthIssue(
                issue_id=HealthIssue.generate_issue_id(
                    "unknown_node", target, with_discriminator(node_type, identity)
                ),
                category=IssueCategory.WORKFLOW,
                severity=IssueSeverity.INFO,
                title="Unknown Node Type",
                summary=f"Node type '{node_type}' ({identity.label}) is not in the known node registry",
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
    identities: List[NodeIdentity],
) -> List[HealthIssue]:
    """Check for obvious parameter anti-patterns."""
    issues: List[HealthIssue] = []

    for identity in identities:
        node = identity.node
        node_type = node.get("type", "")
        if not isinstance(node_type, str):
            # `"KSampler" in None` raises; a type that is not a string is not a node name here either.
            node_type = ""
        node_title = node.get("title", node_type)
        widgets_values = node.get("widgets_values", [])

        if not isinstance(widgets_values, list):
            continue

        # Get widget names from inputs (if available) to map values
        inputs = node.get("inputs", [])
        outputs = node.get("outputs", [])

        # For KSampler and similar nodes, check common parameters
        if "KSampler" in node_type or "Sampler" in node_type:
            issues.extend(_check_sampler_params(identity, node_title, node_type, widgets_values))

        # For EmptyLatentImage, check resolution
        if "EmptyLatentImage" in node_type or "LatentImage" in node_type:
            issues.extend(_check_latent_params(identity, node_title, node_type, widgets_values))

        # Generic widget value checks
        issues.extend(_check_generic_widget_values(identity, node_title, node_type, widgets_values))

    return issues


def _check_sampler_params(
    identity: NodeIdentity,
    node_title: str,
    node_type: str,
    widgets_values: List[Any],
) -> List[HealthIssue]:
    """Check KSampler-type nodes for anti-patterns."""
    issues: List[HealthIssue] = []
    node_id = identity.node_id

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
                        "high_steps", target, with_discriminator(f"{value}", identity)
                    ),
                    category=IssueCategory.PERFORMANCE,
                    severity=IssueSeverity.WARNING,
                    title="Very High Step Count",
                    summary=f"Node '{node_title}' ({identity.label}) has {int(value)} steps, which may be excessive",
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
                        "high_cfg", target, with_discriminator(f"{value}", identity)
                    ),
                    category=IssueCategory.WORKFLOW,
                    severity=IssueSeverity.INFO,
                    title="Very High CFG Value",
                    summary=f"Node '{node_title}' ({identity.label}) has CFG {value}, which may produce artifacts",
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
    identity: NodeIdentity,
    node_title: str,
    node_type: str,
    widgets_values: List[Any],
) -> List[HealthIssue]:
    """Check latent image nodes for resolution anti-patterns."""
    issues: List[HealthIssue] = []
    node_id = identity.node_id

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
            issue_id=HealthIssue.generate_issue_id("high_width", target, with_discriminator(f"{width}", identity)),
            category=IssueCategory.PERFORMANCE,
            severity=IssueSeverity.WARNING,
            title="Very High Resolution Width",
            summary=f"Node '{node_title}' ({identity.label}) has width {width}px, which requires significant VRAM",
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
            issue_id=HealthIssue.generate_issue_id("high_height", target, with_discriminator(f"{height}", identity)),
            category=IssueCategory.PERFORMANCE,
            severity=IssueSeverity.WARNING,
            title="Very High Resolution Height",
            summary=f"Node '{node_title}' ({identity.label}) has height {height}px, which requires significant VRAM",
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
            issue_id=HealthIssue.generate_issue_id("high_batch", target, with_discriminator(f"{batch_size}", identity)),
            category=IssueCategory.PERFORMANCE,
            severity=IssueSeverity.WARNING,
            title="Very High Batch Size",
            summary=f"Node '{node_title}' ({identity.label}) has batch size {batch_size}, which multiplies VRAM usage",
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
    identity: NodeIdentity,
    node_title: str,
    node_type: str,
    widgets_values: List[Any],
) -> List[HealthIssue]:
    """Check generic widget values for common anti-patterns."""
    issues: List[HealthIssue] = []
    node_id = identity.node_id

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
                    "suspicious_value", target, with_discriminator(f"{idx}:{value}", identity)
                ),
                category=IssueCategory.WORKFLOW,
                severity=IssueSeverity.INFO,
                title="Unusually Large Parameter Value",
                summary=f"Node '{node_title}' ({identity.label}) has an unusually large value: {value}",
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


def _check_duplicate_identities(identities: List[NodeIdentity]) -> List[HealthIssue]:
    """Report each group of nodes that share an ID once, without ever targeting one of them."""
    groups: Dict[str, List[NodeIdentity]] = {}
    for identity in identities:
        if identity.state == "duplicate":
            groups.setdefault(str(valid_node_id(identity.node.get("id"))), []).append(identity)

    issues: List[HealthIssue] = []
    for members in list(groups.values())[:MAX_DUPLICATE_GROUPS]:
        # IMPORTANT: the identity is shown only through the bounded, content-free component; the raw id
        # of a workflow file is untrusted and may be 1024 characters of arbitrary text.
        component = safe_execution_id_component(members[0].node.get("id"))
        positions = ", ".join(
            f"nodes[{member.position}]" for member in members[:MAX_DUPLICATE_POSITIONS]
        )
        extra = len(members) - MAX_DUPLICATE_POSITIONS
        if extra > 0:
            positions += f" and {extra} more"
        target = IssueTarget()
        issues.append(HealthIssue(
            issue_id=HealthIssue.generate_issue_id("duplicate_node_id", target, component),
            category=IssueCategory.WORKFLOW,
            severity=IssueSeverity.WARNING,
            title="Duplicate Node ID",
            summary=f"Node ID '{component}' is used by {len(members)} nodes, so none of them can be located",
            evidence=[
                f"Occurrences: {len(members)}",
                f"Positions: {positions}",
                "Findings for these nodes are reported without a node target",
            ],
            recommendation=[
                "Save the workflow again so each node has a unique ID",
                "A hand-edited or merged workflow file can contain repeated node IDs",
            ],
            target=target,
        ))

    skipped = len(groups) - len(issues)
    if skipped > 0 and issues:
        issues[-1].evidence.append(f"... and {skipped} more duplicate groups")
    return issues
