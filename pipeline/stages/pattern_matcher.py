import logging
import re
from typing import List, Tuple, Optional, Any
from ..base import PipelineStage
from ..context import AnalysisContext
from ..plugins import discover_plugins
try:
    from config import CONFIG
except ImportError:
    import sys
    import os
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
    from config import CONFIG

# Import dependencies (wrappers usually)
try:
    from i18n import get_suggestion, ERROR_KEYS
    from pattern_loader import get_pattern_loader
    # analyzer import removed to avoid circular dependency
except ImportError:
    import sys
    import os
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
    from i18n import get_suggestion, ERROR_KEYS
    from pattern_loader import get_pattern_loader

logger = logging.getLogger(__name__)

def _infer_category_from_key(error_key: str) -> str:
    """
    Infer error category from error_key for statistics tracking.
    Duplicated from analyzer.py to avoid circular imports.
    """
    key_lower = error_key.lower()
    
    if any(keyword in key_lower for keyword in ['oom', 'memory', 'allocation']):
        return 'memory'
    if any(keyword in key_lower for keyword in ['safetensors', 'checkpoint', 'model', 'lora', 'vae']):
        return 'model_loading'
    if any(keyword in key_lower for keyword in ['validation', 'missing_input', 'type_mismatch', 'dimension', 'shape']):
        return 'workflow'
    if any(keyword in key_lower for keyword in ['cuda', 'cudnn', 'torch', 'mps', 'insightface', 'module']):
        return 'framework'
    return 'generic'

class PatternMatcherStage(PipelineStage):
    """
    Stage 2: Pattern Matching.
    Tries to match errors using:
    1. Community Plugins (highest priority)
    2. PatternLoader (JSON patterns)
    3. Legacy Hardcoded Patterns (fallback)
    """
    
    def __init__(self, legacy_patterns: List[Tuple[str, str, bool]] = None, load_plugins=None):
        self._name = "PatternMatcherStage"
        self.stage_id = "pattern_matcher"
        self.requires = ["sanitized_traceback"]
        self.provides = [
            "suggestion",
            "metadata.matched_pattern_id",
            "metadata.category",
            "metadata.priority",
            "metadata.match_source",
        ]
        self.version = "1.0"
        self.legacy_patterns = legacy_patterns or []
        self.plugins = []
        if load_plugins is None:
            load_plugins = getattr(CONFIG, "enable_community_plugins", False)
        if load_plugins:
            # We assume plugins are in pipeline/plugins/community
            import pathlib
            plugin_dir = pathlib.Path(__file__).parent.parent / "plugins" / "community"
            self.plugins = discover_plugins(plugin_dir)

    @property
    def name(self) -> str:
        return self._name

    def process(self, context: AnalysisContext) -> None:
        text_to_analyze = context.sanitized_traceback
        
        if not text_to_analyze:
            return

        # 1. Try Plugins
        for matcher_func in self.plugins:
            try:
                result = matcher_func(text_to_analyze)
                plugin_id = getattr(matcher_func, "__plugin_id__", None) or "community.plugin"
                normalized = self._normalize_plugin_result(result, plugin_id)
                if normalized:
                    suggestion, metadata, promoted = normalized
                    context.suggestion = suggestion
                    context.metadata.setdefault("plugin", {})
                    context.metadata["plugin"][plugin_id] = metadata
                    context.metadata.update(promoted)
                    context.add_metadata("match_source", "plugin")
                    return  # Short-circuit
            except Exception as e:
                logger.warning(f"Plugin matcher failed: {e}")

        # 2. Try PatternLoader (JSON)
        try:
            loader = get_pattern_loader()
            result = loader.match(text_to_analyze)
            if result:
                error_key, groups = result
                self._apply_suggestion(context, error_key, groups, source="json_loader")
                return  # Short-circuit
        except Exception as e:
            logger.warning(f"PatternLoader match failed: {e}")

        # 3. Try Legacy Patterns
        for pattern, error_key, has_groups in self.legacy_patterns:
            try:
                # Compile on the fly or rely on re internal cache
                match = re.search(pattern, text_to_analyze, re.IGNORECASE)
                if match:
                    groups = match.groups() if has_groups else ()
                    self._apply_suggestion(context, error_key, groups, source="legacy_fallback")
                    return  # Short-circuit
            except Exception as e:
                logger.warning(f"Legacy pattern match failed: {e}")
                
        # 4. Generic Fallback (e.g. Autograd) - Copied from original analyzer
        if "grad_fn" in text_to_analyze:
             # autograd_generic
             self._apply_suggestion(context, ERROR_KEYS.get("AUTOGRAD", "autograd_error"), (), source="generic_fallback")


    def _apply_suggestion(self, context: AnalysisContext, error_key: str, groups: tuple, source: str):
        """Helper to format suggestion and update context."""
        suggestion_key = ERROR_KEYS.get(error_key, error_key)
        
        # Build suggestion text
        try:
            if groups:
                suggestion = get_suggestion(suggestion_key, *groups)
            else:
                suggestion = get_suggestion(suggestion_key)
        except Exception:
            suggestion = get_suggestion(suggestion_key)
            
        context.suggestion = suggestion
        
        # Get Pattern Info for metadata
        try:
            loader = get_pattern_loader()
            pattern_info = loader.get_pattern_info(error_key)
        except Exception:
            pattern_info = None

        # Build Metadata
        category = "generic"
        priority = 50
        matched_id = error_key
        
        if pattern_info:
            matched_id = pattern_info.get('id', error_key)
            category = pattern_info.get('category', category)
            priority = pattern_info.get('priority', priority)
        else:
            # Use local inference helper
            try:
                 category = _infer_category_from_key(suggestion_key)
            except Exception:
                 pass

        context.metadata.update({
            'matched_pattern_id': matched_id,
            'category': category,
            'priority': priority,
            'match_source': source
        })

    def _normalize_plugin_result(self, result: Any, plugin_id: str):
        if not result:
            return None

        suggestion = None
        metadata = {}

        if isinstance(result, dict):
            suggestion = result.get("suggestion") or result.get("message")
            metadata = result.get("metadata", {})
        elif isinstance(result, (tuple, list)) and len(result) >= 2:
            suggestion = result[0]
            metadata = result[1]
        else:
            logger.warning(f"Plugin {plugin_id} returned unsupported result type")
            return None

        if not isinstance(suggestion, str) or not suggestion.strip():
            logger.warning(f"Plugin {plugin_id} returned empty suggestion")
            return None

        if not isinstance(metadata, dict):
            metadata = {}

        promoted = {}
        if "matched_pattern_id" in metadata:
            promoted["matched_pattern_id"] = metadata["matched_pattern_id"]
        if "category" in metadata:
            promoted["category"] = metadata["category"]
        if "priority" in metadata:
            promoted["priority"] = metadata["priority"]

        promoted.setdefault("matched_pattern_id", plugin_id)
        promoted.setdefault("category", "plugin")
        promoted.setdefault("priority", 100)

        return suggestion, metadata, promoted
