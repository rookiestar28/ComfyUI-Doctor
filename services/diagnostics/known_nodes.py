"""Which node types count as known for the workflow lint.

``Unknown Node Type`` should mean "the running host does not know this type". The host's own registry
answers that exactly, so it is consulted first; a static list covers what the registry cannot (the
frontend's virtual nodes) and every run without a host (standalone checks, tests).
"""

import sys
from collections.abc import Mapping
from typing import Any, FrozenSet, Optional

# Known core ComfyUI node types (not exhaustive, but covers common cases)
# This helps distinguish between "missing custom node" vs "typo in node type"
STATIC_KNOWN_CORE_NODE_TYPES: FrozenSet[str] = frozenset({
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
    "PrimitiveNode", "Reroute", "Note", "MarkdownNote",
    "ComfySwitchNode", "ComfySoftSwitchNode", "BranchNode",
    # First-party names of the host's nodes.py that the list above did not cover
    "UNETLoader", "DualCLIPLoader", "EmptyImage", "LoadImageOutput", "InpaintModelConditioning",
    "CLIPVisionEncode", "StyleModelApply", "unCLIPConditioning", "unCLIPCheckpointLoader",
    "DiffControlNetLoader", "DiffusersLoader", "GLIGENTextBoxApply", "ConditioningMultiply",
    "ConditioningSetAreaStrength", "ConditioningSetTimestepRange",
})

# A mapping that lacks these is not a ComfyUI host registry. The package's own ``nodes.py`` (one debug
# node) is importable as a top-level ``nodes`` module in tests and standalone runs; trusting it would
# make every core node look unknown.
HOST_REGISTRY_ANCHORS = ("KSampler", "CheckpointLoaderSimple", "VAEDecode", "CLIPTextEncode")


def _host_registry() -> Optional[Mapping]:
    """The host's ``NODE_CLASS_MAPPINGS`` if it is already loaded and looks like the host's, else None.

    IMPORTANT: read ``sys.modules`` only. Importing ``nodes`` here would execute whichever ``nodes``
    module the import path finds first, and ``services.prompt_helpers`` already resolves the relative
    ``..nodes`` to this package's own one-node module. Any failure means "no registry".
    """
    try:
        mapping = getattr(sys.modules.get("nodes"), "NODE_CLASS_MAPPINGS", None)
        if isinstance(mapping, Mapping) and all(anchor in mapping for anchor in HOST_REGISTRY_ANCHORS):
            return mapping
    except Exception:
        pass
    return None


def host_node_registry() -> Optional[Mapping]:
    """The host's node registry for other services (the failed node's required inputs), or None.

    The same guarded lookup the workflow lint uses: ``sys.modules`` only, and only a mapping that carries the
    core anchor names. It never imports anything.
    """
    return _host_registry()


def is_known_node_type(node_type: Any) -> bool:
    """True for a non-empty string that the static list or the running host's registry knows."""
    if not isinstance(node_type, str) or not node_type:
        return False
    if node_type in STATIC_KNOWN_CORE_NODE_TYPES:
        return True
    mapping = _host_registry()
    if mapping is None:
        return False
    try:
        return node_type in mapping
    except Exception:
        # A registry that is being mutated or is hostile must not break the check.
        return False


# A legacy group node is serialized with the type ``workflow>Name``; the name is the group's own and is never
# a registered host class. Matching is exact and case-sensitive on purpose.
WORKFLOW_GROUP_NODE_PREFIX = "workflow>"

# The workflow file is untrusted input: the walk over nested subgraph definitions is bounded.
MAX_LOCAL_DEFINITION_DEPTH = 16
MAX_LOCAL_DEFINITIONS = 2000


def collect_workflow_local_node_types(workflow: Any) -> FrozenSet[str]:
    """The ids of the subgraphs this workflow defines (``definitions.subgraphs[].id``), nested ones included.

    A node whose ``type`` is one of these ids is an instance of a subgraph defined in the same file, not a
    node the host failed to register. Only non-empty string ids count and every other shape contributes
    nothing. The walk is iterative and capped (depth and number of definitions); past a cap the remaining
    definitions are simply not recognized, so their instances keep the finding they had before.
    """
    found = set()
    seen = 0
    stack = [(workflow, 0)]
    while stack:
        scope, depth = stack.pop()
        definitions = scope.get("definitions") if isinstance(scope, dict) else None
        subgraphs = definitions.get("subgraphs") if isinstance(definitions, dict) else None
        if not isinstance(subgraphs, list):
            continue
        for definition in subgraphs:
            if not isinstance(definition, dict):
                continue
            seen += 1
            if seen > MAX_LOCAL_DEFINITIONS:
                return frozenset(found)
            definition_id = definition.get("id")
            if isinstance(definition_id, str) and definition_id:
                found.add(definition_id)
            if depth + 1 < MAX_LOCAL_DEFINITION_DEPTH:
                stack.append((definition, depth + 1))
    return frozenset(found)


def is_workflow_local_node_type(node_type: Any, local_types: FrozenSet[str] = frozenset()) -> bool:
    """True for a non-empty string that names a subgraph of this workflow or uses the group-node convention."""
    if not isinstance(node_type, str) or not node_type:
        return False
    if node_type.startswith(WORKFLOW_GROUP_NODE_PREFIX):
        return True
    return node_type in local_types
