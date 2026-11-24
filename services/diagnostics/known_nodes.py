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
