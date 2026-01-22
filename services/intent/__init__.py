"""
F14 Intent Signature System (ISS)

Deterministic inference of user intent from workflow + runtime signals.

Architecture (P2):
- definitions: Builtin intent definitions (JSON)
- extractor: Signal extraction from workflow
- scorer: Intent matching with confidence calculation

ISS is explicitly NOT:
- ML/LLM-based (deterministic rules only)
- Remote/cloud-dependent (all local)
- PII-capturing (sanitized signals only)
"""

import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

from services.diagnostics.models import (
    IntentSignature,
    IntentMatch,
    SignalEvidence,
    SignalSource,
)

logger = logging.getLogger("comfyui-doctor.intent")


# ============================================================================
# Intent Definitions (P2 - will be loaded from JSON)
# ============================================================================

# Schema version for ISS
ISS_SCHEMA_VERSION = "1.0"

# Placeholder intent definitions for P0
# These will be replaced with loaded JSON definitions in P2
BUILTIN_INTENTS: Dict[str, Dict[str, Any]] = {
    "txt2img": {
        "id": "txt2img",
        "name": "Text to Image",
        "description": "Generate image from text prompt",
        "required_signals": ["node_type.CLIPTextEncode", "node_type.KSampler"],
        "positive_signals": ["node_type.EmptyLatentImage"],
        "negative_signals": ["node_type.LoadImage", "node_type.IPAdapter"],
        "stage": "generation",
    },
    "img2img": {
        "id": "img2img",
        "name": "Image to Image",
        "description": "Transform existing image",
        "required_signals": ["node_type.LoadImage", "node_type.KSampler"],
        "positive_signals": ["node_type.VAEEncode"],
        "negative_signals": [],
        "stage": "generation",
    },
    "inpainting": {
        "id": "inpainting",
        "name": "Inpainting",
        "description": "Fill in masked regions of image",
        "required_signals": ["node_type.LoadImage", "node_type.LoadImageMask"],
        "positive_signals": ["node_type.SetLatentNoiseMask"],
        "negative_signals": [],
        "stage": "generation",
    },
    "upscaling": {
        "id": "upscaling",
        "name": "Upscaling",
        "description": "Increase image resolution",
        "required_signals": [],
        "positive_signals": [
            "node_type.UpscaleModelLoader",
            "node_type.ImageUpscaleWithModel",
            "node_type.LatentUpscale",
        ],
        "negative_signals": [],
        "stage": "postprocess",
    },
    "controlnet": {
        "id": "controlnet",
        "name": "ControlNet Guided",
        "description": "Generation guided by ControlNet",
        "required_signals": ["node_type.ControlNetLoader", "node_type.ControlNetApply"],
        "positive_signals": [],
        "negative_signals": [],
        "stage": "generation",
    },
    "ipadapter": {
        "id": "ipadapter",
        "name": "IP-Adapter Style Transfer",
        "description": "Style transfer using IP-Adapter",
        "required_signals": ["node_type.IPAdapter"],
        "positive_signals": ["node_type.IPAdapterModelLoader"],
        "negative_signals": [],
        "stage": "generation",
    },
    "lora": {
        "id": "lora",
        "name": "LoRA Fine-tuning",
        "description": "Using LoRA for style/concept",
        "required_signals": ["node_type.LoraLoader"],
        "positive_signals": [],
        "negative_signals": [],
        "stage": "setup",
    },
    "video": {
        "id": "video",
        "name": "Video Generation",
        "description": "Generate or process video",
        "required_signals": [],
        "positive_signals": [
            "node_type.AnimateDiff",
            "node_type.VHS_",
            "node_type.LoadVideo",
        ],
        "negative_signals": [],
        "stage": "generation",
    },
}


# ============================================================================
# Signal Extractor (P2 - skeleton)
# ============================================================================

class SignalExtractor:
    """
    Extracts signals from workflow for intent matching.

    Signal types:
    - node_type.X: Presence of node type X
    - node_count.X: Count of node type X
    - connection.X_Y: Connection from X to Y
    - widget.X: Widget value pattern
    """

    def extract(self, workflow: Dict[str, Any]) -> List[SignalEvidence]:
        """
        Extract signals from workflow.

        Args:
            workflow: Workflow JSON (graph format)

        Returns:
            List of extracted signals
        """
        signals: List[SignalEvidence] = []

        nodes = workflow.get("nodes", [])
        if not isinstance(nodes, list):
            return signals

        # Extract node type signals
        node_types: Dict[str, List[int]] = {}
        for node in nodes:
            if not isinstance(node, dict):
                continue
            node_type = node.get("type", "")
            node_id = node.get("id")
            if node_type:
                if node_type not in node_types:
                    node_types[node_type] = []
                if node_id is not None:
                    node_types[node_type].append(node_id)

        # Create signals for each node type
        for node_type, node_ids in node_types.items():
            # Presence signal
            signals.append(SignalEvidence(
                signal_id=f"node_type.{node_type}",
                weight=1.0,
                value=True,
                source=SignalSource.WORKFLOW,
                node_ids=node_ids,
                explain=f"Node type '{node_type}' present ({len(node_ids)} instance(s))",
            ))

            # Count signal (if multiple)
            if len(node_ids) > 1:
                signals.append(SignalEvidence(
                    signal_id=f"node_count.{node_type}",
                    weight=0.5,
                    value=len(node_ids),
                    source=SignalSource.WORKFLOW,
                    node_ids=node_ids,
                    explain=f"{len(node_ids)} instances of '{node_type}'",
                ))

        return signals


# ============================================================================
# Intent Scorer (P2 - skeleton)
# ============================================================================

class IntentScorer:
    """
    Scores intents based on extracted signals.

    Scoring algorithm:
    - Required signals must all be present (confidence = 0 if missing)
    - Positive signals add to confidence
    - Negative signals subtract from confidence
    - Final confidence clamped to [0, 1]
    """

    def __init__(self, intents: Optional[Dict[str, Dict[str, Any]]] = None):
        """
        Initialize scorer with intent definitions.

        Args:
            intents: Intent definitions dict (default: BUILTIN_INTENTS)
        """
        self.intents = intents or BUILTIN_INTENTS
        self.extractor = SignalExtractor()

    async def compute(
        self,
        workflow: Dict[str, Any],
        workflow_hash: str,
        top_k: int = 3,
    ) -> IntentSignature:
        """
        Compute intent signature for a workflow.

        Args:
            workflow: Workflow JSON
            workflow_hash: Pre-computed workflow hash
            top_k: Number of top intents to return

        Returns:
            IntentSignature with matched intents
        """
        # Extract signals
        signals = self.extractor.extract(workflow)
        signal_ids = {s.signal_id for s in signals}
        signal_map = {s.signal_id: s for s in signals}

        # Score each intent
        scored_intents: List[tuple[str, float, List[SignalEvidence]]] = []

        for intent_id, intent_def in self.intents.items():
            required = intent_def.get("required_signals", [])
            positive = intent_def.get("positive_signals", [])
            negative = intent_def.get("negative_signals", [])

            # Check required signals
            required_present = all(
                any(sig_id.startswith(req) or req in sig_id for sig_id in signal_ids)
                for req in required
            )

            if not required_present and required:
                continue  # Skip if required signals missing

            # Calculate confidence
            confidence = 0.0
            evidence: List[SignalEvidence] = []

            # Required signals contribute 0.3 each
            for req in required:
                matching = [s for s in signals if req in s.signal_id]
                if matching:
                    confidence += 0.3
                    evidence.extend(matching[:1])  # Include one evidence per signal

            # Positive signals contribute 0.15 each
            for pos in positive:
                matching = [s for s in signals if pos in s.signal_id]
                if matching:
                    confidence += 0.15
                    evidence.extend(matching[:1])

            # Negative signals reduce by 0.2 each
            for neg in negative:
                matching = [s for s in signals if neg in s.signal_id]
                if matching:
                    confidence -= 0.2

            # Clamp confidence
            confidence = max(0.0, min(1.0, confidence))

            if confidence > 0:
                scored_intents.append((intent_id, confidence, evidence))

        # Sort by confidence and take top_k
        scored_intents.sort(key=lambda x: x[1], reverse=True)
        top_intents = scored_intents[:top_k]

        # Build IntentMatches
        intent_matches: List[IntentMatch] = []
        for intent_id, confidence, evidence in top_intents:
            intent_def = self.intents[intent_id]
            intent_matches.append(IntentMatch(
                intent_id=intent_id,
                confidence=round(confidence, 2),
                stage=intent_def.get("stage"),
                evidence=evidence,
            ))

        # Global signals (not tied to specific intent)
        global_signals = [s for s in signals if s.weight >= 1.0][:5]

        return IntentSignature(
            schema_version=ISS_SCHEMA_VERSION,
            timestamp=datetime.utcnow().isoformat() + "Z",
            workflow_hash=workflow_hash,
            top_intents=intent_matches,
            global_signals=global_signals,
        )


# ============================================================================
# Module Interface
# ============================================================================

_scorer: Optional[IntentScorer] = None


def get_intent_scorer() -> IntentScorer:
    """Get or create the global IntentScorer instance."""
    global _scorer
    if _scorer is None:
        _scorer = IntentScorer()
    return _scorer


def init_intent_system():
    """
    Initialize the intent signature system.

    Called during module initialization to:
    1. Load intent definitions
    2. Register scorer with diagnostics runner
    """
    from services.diagnostics import get_diagnostics_runner

    scorer = get_intent_scorer()
    runner = get_diagnostics_runner()
    runner.set_intent_scorer(scorer)

    logger.info(f"Intent system initialized with {len(BUILTIN_INTENTS)} builtin intents")


__all__ = [
    "ISS_SCHEMA_VERSION",
    "BUILTIN_INTENTS",
    "SignalExtractor",
    "IntentScorer",
    "get_intent_scorer",
    "init_intent_system",
]
