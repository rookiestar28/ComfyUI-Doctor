"""
Error Analyzer for ComfyUI Runtime Diagnostics.
Analyzes Python tracebacks and provides human-readable suggestions for common errors.
Refactored to use Plugin-based Analysis Pipeline (A6).
"""

import re
import functools
import logging
from dataclasses import dataclass
from typing import Optional, Tuple, List, Dict, Any

# A6: Import Pipeline Components
try:
    from pipeline import AnalysisPipeline, AnalysisContext, NodeContext
    from pipeline.stages import SanitizerStage, PatternMatcherStage, ContextEnhancerStage
    # Ensure i18n is available for dependencies
    from i18n import get_suggestion, ERROR_KEYS
except ImportError:
    # Fallback for relative imports (tests/dev)
    import sys
    import os
    sys.path.append(os.path.dirname(__file__))
    from pipeline import AnalysisPipeline, AnalysisContext, NodeContext
    from pipeline.stages import SanitizerStage, PatternMatcherStage, ContextEnhancerStage
    from i18n import get_suggestion, ERROR_KEYS

# Keep PATTERNS for Legacy Fallback (Stage 2)
# Pattern definitions: (regex_pattern, error_key, has_groups)
# Patterns are checked in order, first match wins
PATTERNS: List[Tuple[str, str, bool]] = [
    # SafeTensors Error
    (r"safetensors_rust.SafetensorError: Error while deserializing header",
     ERROR_KEYS["SAFETENSORS_ERROR"], False),

    # CUDNN Error
    (r"RuntimeError: cuDNN error: CUDNN_STATUS_EXECUTION_FAILED",
     ERROR_KEYS["CUDNN_ERROR"], False),
    
    # Missing InsightFace
    (r"ModuleNotFoundError: No module named 'insightface'",
     ERROR_KEYS["MISSING_INSIGHTFACE"], False),

    # Model/VAE Mismatch (autograd generic but specific text)
    (r"RuntimeError: element 0 of tensors does not require grad and does not have a grad_fn",
     ERROR_KEYS["MODEL_VAE_MISMATCH"], False),
    
    # MPS OOM
    (r"MPS backend out of memory",
     ERROR_KEYS["MPS_OOM"], False),

    # Invalid Prompt (JSON)
    (r"json.decoder.JSONDecodeError",
     ERROR_KEYS["INVALID_PROMPT"], False),

    # Type mismatch
    (r"RuntimeError: expected scalar type (\w+) but found (\w+)", 
     ERROR_KEYS["TYPE_MISMATCH"], True),
    
    # Dimension mismatch
    (r"RuntimeError: The size of tensor ([a-z]) \((\d+)\) must match the size of tensor ([a-z]) \((\d+)\) at non-singleton dimension (\d+)",
     ERROR_KEYS["DIMENSION_MISMATCH"], True),

    # CUDA OOM (classic)
    (r"CUDA out of memory", 
     ERROR_KEYS["OOM"], False),
    
    # PyTorch OOM (newer format)
    (r"torch\.OutOfMemoryError",
     ERROR_KEYS["TORCH_OOM"], False),

    # Matrix multiplication
    (r"mat1 and mat2 shapes cannot be multiplied",
     ERROR_KEYS["MATRIX_MULT"], False),

    # Device/Type mismatch
    (r"Input type \((\w+)\) and weight type \((\w+)\) should be the same",
     ERROR_KEYS["DEVICE_TYPE"], True),
     
    # Missing module (improved: supports submodules like 'pkg.submodule')
    (r"(?:ModuleNotFoundError|ImportError): No module named ['\"]?([\w.]+)['\"]?",
     ERROR_KEYS["MISSING_MODULE"], True),
    
    # Assertion error
    (r"AssertionError: (.+)",
     ERROR_KEYS["ASSERTION"], True),
    
    # Key error
    (r"KeyError: ['\"](.+)['\"]",
     ERROR_KEYS["KEY_ERROR"], True),
    
    # Attribute error
    (r"AttributeError: '(.+)' object has no attribute '(.+)'",
     ERROR_KEYS["ATTRIBUTE_ERROR"], True),
    
    # Shape mismatch (generic)
    (r"ValueError: (.+) shape (.+) doesn't match (.+)",
     ERROR_KEYS["SHAPE_MISMATCH"], True),
    
    # File not found
    (r"FileNotFoundError: \[Errno 2\] No such file or directory: '(.+)'",
     ERROR_KEYS["FILE_NOT_FOUND"], True),

    # ComfyUI Validation Error (Dynamic inputs mismatch)
    (r"Failed to validate prompt for output \d+:[\s\S]*?\*\s+([^\n]+)\s+\d+:\s*\n\s*-\s+([^\n]+)",
     ERROR_KEYS["VALIDATION_ERROR"], True),

    # Debug Node: Tensor NaN/Inf
    (r"❌ CRITICAL: Tensor contains (NaN|Inf)",
     ERROR_KEYS["TENSOR_NAN_INF"], True),

    # Debug Node: Meta Tensor
    (r"⚠️ Meta Tensor",
     ERROR_KEYS["META_TENSOR"], False),
]

_pipeline_instance = None

def get_pipeline():
    """Singleton accessor for AnalysisPipeline."""
    global _pipeline_instance
    if _pipeline_instance is None:
        stages = [
            SanitizerStage(),
            PatternMatcherStage(legacy_patterns=PATTERNS),
            ContextEnhancerStage(),
            # LLMContextBuilderStage will be added here in Phase 3
        ]
        _pipeline_instance = AnalysisPipeline(stages)
    return _pipeline_instance

# Helper for pre-compiling patterns (used by is_complete_traceback or legacy parts)
@functools.lru_cache(maxsize=64)
def _compile_pattern(pattern: str):
    """Compile and cache a regex pattern."""
    return re.compile(pattern, re.IGNORECASE)


class ErrorAnalyzer:
    """
    Analyzes Python tracebacks and provides human-readable suggestions 
    for common ComfyUI/PyTorch errors.
    
    A6: Now acts as a wrapper around AnalysisPipeline.
    """
    
    @staticmethod
    def _infer_category_from_key(error_key: str) -> str:
        """
        Infer error category from error_key.
        Kept for backward compatibility and internal use by PatternMatcherStage.
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
    
    @staticmethod
    def extract_node_context(traceback_text: str) -> NodeContext:
        """
        Extract ComfyUI node context from a traceback.
        A6: Delegates to ContextEnhancerStage directly.
        """
        if not traceback_text:
            return NodeContext()
            
        # Create a temp context and run just the Enhancer Stage
        # This prevents running full pipeline overhead for just extraction
        # But maintains logic in one place (ContextEnhancerStage)
        ctx = AnalysisContext(traceback=traceback_text)
        enhancer = ContextEnhancerStage()
        enhancer.process(ctx)
        
        return ctx.node_context or NodeContext()
    
    @staticmethod
    def analyze(traceback_text: str) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
        """
        Scans the traceback for known error patterns and returns a suggestion with metadata.
        A6: Delegates to AnalysisPipeline.
        """
        if not traceback_text:
            return (None, None)

        try:
            pipeline = get_pipeline()
            ctx = AnalysisContext(traceback=traceback_text)
            
            # Run the pipeline
            pipeline.run(ctx)
            
            return (ctx.suggestion, ctx.metadata)
            
        except Exception as e:
            logging.error(f"[ErrorAnalyzer] Pipeline failed: {e}", exc_info=True)
            return (None, None)
    
    @staticmethod
    def is_complete_traceback(text: str) -> bool:
        """
        Check if the text contains a complete Python traceback.
        Kept as utility.
        """
        # For standard Python tracebacks
        if "Traceback (most recent call last):" in text:
            error_pattern = r'\n([A-Z][a-zA-Z0-9]*(?:Error|Exception|Warning|Interrupt)):.*'
            has_python_error = bool(re.search(error_pattern, text))
            if has_python_error:
                return True

        # For ComfyUI Validation Errors
        if "Failed to validate prompt for output" in text:
            validation_count = text.count("Failed to validate prompt for output")
            executing_marker = "Executing prompt:" in text

            if executing_marker:
                return True

            has_details = bool(re.search(r'\n[*\-] ', text))
            if has_details and validation_count >= 1:
                lines = text.strip().split('\n')
                if lines:
                    last_line = lines[-1].strip()
                    if "Output will be ignored" in last_line or "Prompt executed" in last_line:
                        return True

        return False

    @staticmethod
    def reload_patterns() -> bool:
        """
        Reload patterns from JSON files.
        Wraps PatternLoader through Pipeline? 
        The Pipeline's PatternMatcherStage holds the plugin list and loader reference.
        The loader is a singleton, so reloading it via get_pattern_loader() works globaly.
        """
        try:
            from pattern_loader import get_pattern_loader
            loader = get_pattern_loader()
            return loader.reload_if_changed()
        except Exception as e:
            logging.warning(f"[ErrorAnalyzer] Failed to reload patterns: {e}")
            return False


