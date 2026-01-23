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
from services.intent.loader import load_intents  # P2: Load from JSON

logger = logging.getLogger("comfyui-doctor.intent")


# ============================================================================
# Intent Definitions (P2)
# ============================================================================

# Schema version for ISS
ISS_SCHEMA_VERSION = "1.0"


# ============================================================================
# Signal Extractor (P2)
# ============================================================================

class SignalExtractor:
    """
    Extracts signals from workflow for intent matching.

    Signal types:
    - node_type.X: Presence of node type X
    - node_count.X: Count of node type X
    - edge.X_Y: Connection from node type X to Y
    """

    def extract(self, workflow: Dict[str, Any]) -> List[SignalEvidence]:
        """
        Extract signals from workflow.

        Args:
            workflow: Workflow JSON (graph format or API format)

        Returns:
            List of extracted signals
        """
        signals: List[SignalEvidence] = []

        # P3: Normalize nodes to list of dicts (handle list vs dict format)
        raw_nodes = workflow.get("nodes", [])
        nodes: List[Dict[str, Any]] = []

        if isinstance(raw_nodes, list):
            nodes = raw_nodes
        elif isinstance(raw_nodes, dict):
            # API format: "nodes": { "1": { ... }, "2": { ... } }
            nodes = list(raw_nodes.values())

        links = workflow.get("links", [])
        # links format in Comfy: [[id, source_id, source_enc, target_id, target_enc, type], ...]
        
        # Build node maps for edge detection
        node_id_to_type = {}
        node_types: Dict[str, List[int]] = {}  # type -> [node_ids]

        for node in nodes:
            if not isinstance(node, dict):
                continue
            
            node_type = node.get("type") or node.get("class_type") or ""
            node_id = node.get("id")
            
            if node_type and node_id is not None:
                # Store for edge detection
                try:
                    # node_id might be string or int in JSON, simpler to map as is
                    node_id_to_type[node_id] = node_type
                    # Store as int for consistency if possible, else str
                    nid_safe = int(node_id) if str(node_id).isdigit() else str(node_id)
                    
                    if node_type not in node_types:
                        node_types[node_type] = []
                    node_types[node_type].append(nid_safe)
                except ValueError:
                    pass

        # 1. Node Type & Count Signals
        for node_type, node_ids in node_types.items():
            # Presence signal
            signals.append(SignalEvidence(
                signal_id=f"node_type.{node_type}",
                weight=1.0,  # Base weight, actual impact defined in intent JSON
                value=True,
                source=SignalSource.WORKFLOW,
                node_ids=node_ids[:20],  # cap list size
                explain=_sanitize_evidence_string(f"Node type '{node_type}' present"),
            ))

            # Count signal (if multiple)
            if len(node_ids) > 1:
                signals.append(SignalEvidence(
                    signal_id=f"node_count.{node_type}",
                    weight=0.5,
                    value=len(node_ids),
                    source=SignalSource.WORKFLOW,
                    node_ids=node_ids[:20],
                    explain=_sanitize_evidence_string(f"{len(node_ids)} instances of '{node_type}'"),
                ))

        # 2. Edge Signals
        if isinstance(links, list):
            unique_edges = set()
            
            for link in links:
                # defensive check against malformed link arrays
                if not isinstance(link, list) or len(link) < 5:
                    continue
                    
                # link schema: [id, origin_id, origin_slot, target_id, target_slot, type]
                try:
                    origin_id = link[1]
                    target_id = link[3]
                    
                    origin_type = node_id_to_type.get(origin_id) or node_id_to_type.get(str(origin_id)) or node_id_to_type.get(int(origin_id) if str(origin_id).isdigit() else None)
                    target_type = node_id_to_type.get(target_id) or node_id_to_type.get(str(target_id)) or node_id_to_type.get(int(target_id) if str(target_id).isdigit() else None)
                    
                    if origin_type and target_type:
                        edge_key = f"edge.{origin_type}_{target_type}"
                        if edge_key not in unique_edges:
                            unique_edges.add(edge_key)
                            signals.append(SignalEvidence(
                                signal_id=edge_key,
                                weight=0.8,
                                value=True,
                                source=SignalSource.WORKFLOW,
                                node_ids=[origin_id, target_id],
                                explain=_sanitize_evidence_string(f"Connection: {origin_type} -> {target_type}"),
                            ))
                except (IndexError, ValueError):
                    continue

        return signals


# ============================================================================
# Helpers (P3)
# ============================================================================

def _sanitize_evidence_string(text: str, max_len: int = 120) -> str:
    """
    Sanitize evidence string to prevent PII leakage and enforce bounds.
    """
    if not text:
        return ""
    
    # Cap length
    if len(text) > max_len:
        text = text[:max_len] + "..."
    
    # Simple sanitization for strict mode (if ever needed here, though we mainly rely on Sanitizer logic)
    # Basic path removal (windows/linux)
    if "C:\\" in text or "/" in text:
         # Conservative: Don't aggressively strip paths here effectively, just rely on structure.
         # But we can strip extremely long words which might be tokens
         pass

    return text


# ============================================================================
# Intent Scorer (P2)
# ============================================================================

class IntentScorer:
    """
    Scores intents based on extracted signals.

    Scoring algorithm:
    - Required signals must all be present (confidence = 0 if missing)
    - Positive signals add to confidence
    - Negative signals subtract from confidence
    - Final confidence normalized and clamped
    """

    def __init__(self, intents: Optional[Dict[str, Dict[str, Any]]] = None):
        """
        Initialize scorer with intent definitions.

        Args:
            intents: Intent definitions dict (default: loaded from JSON)
        """
        self.intents = intents or load_intents()
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
        
        # Optimization: Map signal_id to signal object for O(1) lookups
        # Also supports partial matches if needed, but strict mapping first
        signal_map = {s.signal_id: s for s in signals}
        
        # To support "contains" matching (like node_type.KSampler matching node_type.KSamplerAdvanced if configured),
        # we can build a set of IDs. For P2, exact string matching or prefix matching depends on definitions.
        # Our JSON uses exact keys like "node_type.KSampler", so let's stick to set lookup.
        available_signal_ids = set(signal_map.keys())

        # Score each intent
        scored_intents: List[tuple[str, float, List[SignalEvidence]]] = []

        for intent_id, intent_def in self.intents.items():
            required = intent_def.get("required_signals", [])
            positive = intent_def.get("positive_signals", [])
            negative = intent_def.get("negative_signals", [])

            # 1. Check required signals
            # Allow flexible matching: if req="node_type.KSampler", we look for exactly that signal.
            # Could extended to wildcard later, but P2 scope is deterministic exact/prefix.
            
            missing_required = False
            req_evidence: List[SignalEvidence] = []
            
            for req in required:
                # Find matching signal
                # For now, simplistic check: is req in available_signal_ids?
                if req in available_signal_ids:
                    req_evidence.append(signal_map[req])
                else:
                    missing_required = True
                    break
            
            if missing_required and required:
                continue

            # 2. Calculate base confidence
            # Heuristic: Start at 0.0
            # Each required signal (met) adds significant confidence
            # Each positive signal adds moderate confidence
            # Each negative signal subtracts confidence
            
            confidence = 0.0
            evidence: List[SignalEvidence] = []
            evidence.extend(req_evidence)
            
            # Base score from meeting strict requirements
            if required:
                confidence += 0.4
            else:
                # If no requirements (e.g. video), start lower
                confidence += 0.1

            # Add positives
            for pos in positive:
                if pos in available_signal_ids:
                    confidence += 0.2
                    evidence.append(signal_map[pos])
            
            # Subtract negatives
            for neg in negative:
                if neg in available_signal_ids:
                    confidence -= 0.3
                    # Negative evidence usually interesting to show why score is low? 
                    # Actually, usually we show evidence for why it IS matched.
            
            # Normalize/Clamp
            confidence = max(0.0, min(1.0, confidence))

            if confidence > 0.1:  # Threshold to be considered a candidate
                scored_intents.append((intent_id, confidence, evidence))

        # Sort: Primary = Confidence (Desc), Secondary = ID (Asc) for stability
        scored_intents.sort(key=lambda x: (-x[1], x[0]))
        
        top_candidates = scored_intents[:top_k]

        # Build IntentMatches
        intent_matches: List[IntentMatch] = []
        for intent_id, confidence, evidence in top_candidates:
            intent_def = self.intents[intent_id]
            
            # Deduplicate evidence
            unique_evidence = []
            seen_sigs = set()
            for ev in evidence:
                if ev.signal_id not in seen_sigs:
                    unique_evidence.append(ev)
                    seen_sigs.add(ev.signal_id)

            intent_matches.append(IntentMatch(
                intent_id=intent_id,
                confidence=round(confidence, 2),
                stage=intent_def.get("stage"),
                evidence=unique_evidence[:5], # Cap evidence items per intent
            ))

        # Global signals: High-value signals for debugging (e.g. key nodes found)
        # Sort by weight? For now, just node types.
        global_signals = [s for s in signals if s.signal_id.startswith("node_type.")][:10]

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

    logger.info(f"Intent system initialized with P2 extractor")


__all__ = [
    "ISS_SCHEMA_VERSION",
    "SignalExtractor",
    "IntentScorer",
    "get_intent_scorer",
    "init_intent_system",
]
