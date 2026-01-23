import json
import logging
import os
from typing import Dict, Any, Optional

logger = logging.getLogger("comfyui-doctor.intent.loader")

# Fallback in case JSON is missing or corrupt
FALLBACK_INTENTS = {
    "txt2img": {
        "id": "txt2img",
        "name": "Text to Image",
        "description": "Generate image from text prompt (Fallback)",
        "required_signals": ["node_type.CLIPTextEncode", "node_type.KSampler"],
        "positive_signals": ["node_type.EmptyLatentImage"],
        "negative_signals": ["node_type.LoadImage"],
        "stage": "generation",
    }
}

def load_intents() -> Dict[str, Dict[str, Any]]:
    """
    Load intent definitions from JSON files.
    Returns a unified dictionary of intent definitions.
    Falls back to a minimal set if loading fails.
    """
    definitions_dir = os.path.join(os.path.dirname(__file__), "definitions")
    intents: Dict[str, Dict[str, Any]] = {}
    
    # Ensure directory exists
    if not os.path.exists(definitions_dir):
        logger.warning(f"Intent definitions directory not found: {definitions_dir}. Using fallback.")
        return FALLBACK_INTENTS
        
    builtin_path = os.path.join(definitions_dir, "builtin.intents.json")
    
    try:
        if os.path.exists(builtin_path):
            with open(builtin_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, dict):
                    # Basic validation
                    valid_count = 0
                    for key, val in data.items():
                        if "id" in val and "required_signals" in val:
                            intents[key] = val
                            valid_count += 1
                    logger.info(f"Loaded {valid_count} builtin intents from {builtin_path}")
                else:
                    logger.error(f"Invalid format in {builtin_path}, expected dict")
        else:
             logger.warning(f"Builtin intents file missing: {builtin_path}")
             
    except Exception as e:
        logger.error(f"Failed to load intents from {builtin_path}: {e}")
        # If we failed to load anything, return fallback
        if not intents:
            return FALLBACK_INTENTS

    # If totally empty for some reason, use fallback
    if not intents:
        return FALLBACK_INTENTS
        
    return intents
