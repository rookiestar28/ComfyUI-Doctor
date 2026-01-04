"""
Error Analyzer for ComfyUI Runtime Diagnostics.
Analyzes Python tracebacks and provides human-readable suggestions for common errors.
"""

import re
import functools
import logging
from dataclasses import dataclass
from typing import Optional, Tuple, List, Dict, Any

try:
    from .i18n import get_suggestion, ERROR_KEYS
    from .pattern_loader import get_pattern_loader
except ImportError:
    # Fallback for direct execution (tests)
    from i18n import get_suggestion, ERROR_KEYS
    from pattern_loader import get_pattern_loader


@dataclass
class NodeContext:
    """Context information about the node where an error occurred."""
    node_id: Optional[str] = None
    node_name: Optional[str] = None
    node_class: Optional[str] = None
    custom_node_path: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "node_id": self.node_id,
            "node_name": self.node_name,
            "node_class": self.node_class,
            "custom_node_path": self.custom_node_path,
        }
    
    def is_valid(self) -> bool:
        """Check if any context was extracted."""
        return any([self.node_id, self.node_name, self.node_class])


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
    # Capture only the first error line, not the entire block
    (r"Failed to validate prompt for output \d+:[\s\S]*?\*\s+([^\n]+)\s+\d+:\s*\n\s*-\s+([^\n]+)",
     ERROR_KEYS["VALIDATION_ERROR"], True),

    # Debug Node: Tensor NaN/Inf
    (r"❌ CRITICAL: Tensor contains (NaN|Inf)",
     ERROR_KEYS["TENSOR_NAN_INF"], True),

    # Debug Node: Meta Tensor
    (r"⚠️ Meta Tensor",
     ERROR_KEYS["META_TENSOR"], False),
]

# ComfyUI-specific patterns for extracting node context
NODE_CONTEXT_PATTERNS = [
    # Pattern: Validation error format "* NodeName NodeID:" (highest priority)
    r"\*\s+([A-Za-z0-9_]+)\s+(\d+):",

    # Pattern: "Error occurred in node #123: NodeName" (common format)
    r"(?:ERROR|error)\s*(?:occurred\s*)?(?:on|in)\s*node\s*[#:]?\s*(\d+)(?:\s*[:\-]\s*(.+?))?(?:\s*\n|\s*$)",

    # Pattern: execution.py logs like "got prompt 123" with node info
    r"Executing node (\d+),?\s*[tT]itle:\s*(.+?)(?:,|\n|$)",

    # Pattern: "!!! Exception during processing node #123 !!!"
    r"Exception during processing.*?node\s*[#:]?\s*(\d+)",

    # Pattern: ComfyUI prompt error format
    r"Prompt executed.*?node\s*[#:]?\s*(\d+)(?:\s*[:\-]\s*(.+?))?(?:\)|$)",

    # Pattern: Node class from traceback File path
    r"custom_nodes[/\\]([^/\\]+)[/\\].*?\.py",

    # Pattern: Class name in traceback (self.<method> in <ClassName>)
    r"in\s+(\w+Node)\.",

    # Pattern: ComfyUI internal node class detection
    r"class\s+'([^']+Node)'",
]


# P3: Pre-compile and cache regex patterns for performance
@functools.lru_cache(maxsize=64)
def _compile_pattern(pattern: str):
    """Compile and cache a regex pattern."""
    return re.compile(pattern, re.IGNORECASE)


class ErrorAnalyzer:
    """
    Analyzes Python tracebacks and provides human-readable suggestions 
    for common ComfyUI/PyTorch errors.
    """
    
    @staticmethod
    def _infer_category_from_key(error_key: str) -> str:
        """
        Infer error category from error_key for statistics tracking.
        
        Categories:
        - memory: OOM errors, memory allocation failures
        - model_loading: Model/checkpoint loading errors
        - workflow: Validation, missing inputs, type mismatches
        - framework: CUDA, PyTorch, library errors
        - generic: Other errors
        
        Args:
            error_key: The error key from patterns (lowercased)
        
        Returns:
            Category string
        """
        key_lower = error_key.lower()
        
        # Memory-related errors
        if any(keyword in key_lower for keyword in ['oom', 'memory', 'allocation']):
            return 'memory'
        
        # Model loading errors
        if any(keyword in key_lower for keyword in ['safetensors', 'checkpoint', 'model', 'lora', 'vae']):
            return 'model_loading'
        
        # Workflow errors (validation, inputs, types)
        if any(keyword in key_lower for keyword in ['validation', 'missing_input', 'type_mismatch', 'dimension', 'shape']):
            return 'workflow'
        
        # Framework errors (CUDA, PyTorch, libraries)
        if any(keyword in key_lower for keyword in ['cuda', 'cudnn', 'torch', 'mps', 'insightface', 'module']):
            return 'framework'
        
        return 'generic'
    
    @staticmethod
    def extract_node_context(traceback_text: str) -> NodeContext:
        """
        Extract ComfyUI node context from a traceback.
        
        Attempts to find:
        - Node ID (numeric identifier)
        - Node Name (display name / title)
        - Node Class (Python class name)
        - Custom Node Path (which custom_nodes folder)
        
        Args:
            traceback_text: The full traceback text to analyze.
            
        Returns:
            NodeContext object with extracted information.
        """
        context = NodeContext()
        
        if not traceback_text:
            return context
        
        # Try to extract node ID and name
        for idx, pattern in enumerate(NODE_CONTEXT_PATTERNS[:5]):
            match = re.search(pattern, traceback_text, re.IGNORECASE)
            if match:
                groups = match.groups()
                if groups:
                    # First pattern (* NodeName NodeID:) has reversed order
                    if idx == 0:
                        # First group is node name, second is node ID
                        if len(groups) > 0 and groups[0]:
                            context.node_name = groups[0].strip()
                        if len(groups) > 1 and groups[1] and groups[1].isdigit():
                            context.node_id = groups[1]
                    else:
                        # Other patterns: First group is usually node ID
                        if groups[0] and groups[0].isdigit():
                            context.node_id = groups[0]
                        # Second group (if exists) is usually node name
                        if len(groups) > 1 and groups[1]:
                            context.node_name = groups[1].strip()
                break
        
        # Extract custom node folder name
        custom_node_match = re.search(NODE_CONTEXT_PATTERNS[5], traceback_text)
        if custom_node_match:
            context.custom_node_path = custom_node_match.group(1)

        # Extract node class name
        for pattern in NODE_CONTEXT_PATTERNS[6:]:
            class_match = re.search(pattern, traceback_text)
            if class_match:
                context.node_class = class_match.group(1)
                break
        
        return context
    
    @staticmethod
    def analyze(traceback_text: str) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
        """
        Scans the traceback for known error patterns and returns a suggestion with metadata.

        Architecture (v1.3.0+):
        - Try PatternLoader first (JSON-based patterns with hot-reload)
        - Fallback to hardcoded PATTERNS if PatternLoader fails
        - Ensures error analysis always works even if JSON loading fails

        Args:
            traceback_text: The full traceback text to analyze.

        Returns:
            Tuple of (suggestion_string, pattern_metadata)
            - suggestion_string: Formatted suggestion, or None if no match
            - pattern_metadata: Dict with keys 'matched_pattern_id', 'category', 'priority',
              or None if no match
        """
        if not traceback_text:
            return (None, None)

        # Try PatternLoader first (JSON-based patterns)
        try:
            loader = get_pattern_loader()
            result = loader.match(traceback_text)
            if result:
                error_key, groups = result
                # Map error_key (e.g., "MISSING_INPUT") to suggestion key (e.g., "missing_input")
                suggestion_key = ERROR_KEYS.get(error_key, error_key)
                
                # Build suggestion text
                try:
                    if groups:
                        suggestion = get_suggestion(suggestion_key, *groups)
                    else:
                        suggestion = get_suggestion(suggestion_key)
                except Exception:
                    suggestion = get_suggestion(suggestion_key)
                
                # Build pattern metadata for statistics (F4)
                try:
                    pattern_info = loader.get_pattern_info(error_key)
                    if pattern_info:
                        metadata = {
                            'matched_pattern_id': pattern_info.get('id', error_key),
                            'category': pattern_info.get('category', ErrorAnalyzer._infer_category_from_key(suggestion_key)),
                            'priority': pattern_info.get('priority', 50)
                        }
                    else:
                        # Fallback metadata if pattern_info unavailable
                        metadata = {
                            'matched_pattern_id': error_key,
                            'category': ErrorAnalyzer._infer_category_from_key(suggestion_key),
                            'priority': 50
                        }
                except Exception:
                    # Minimal metadata on error
                    metadata = {
                        'matched_pattern_id': error_key,
                        'category': ErrorAnalyzer._infer_category_from_key(suggestion_key),
                        'priority': 50
                    }
                
                return (suggestion, metadata)
        except Exception as e:
            # Log warning but continue to fallback
            logging.warning(f"[ErrorAnalyzer] PatternLoader failed, using fallback: {e}")

        # Fallback to hardcoded PATTERNS (for reliability)
        for pattern, error_key, has_groups in PATTERNS:
            match = _compile_pattern(pattern).search(traceback_text)
            if match:
                try:
                    if has_groups and match.groups():
                        suggestion = get_suggestion(error_key, *match.groups())
                    else:
                        suggestion = get_suggestion(error_key)
                except Exception:
                    suggestion = get_suggestion(error_key)
                
                # Build metadata for fallback patterns
                metadata = {
                    'matched_pattern_id': error_key,
                    'category': ErrorAnalyzer._infer_category_from_key(error_key),
                    'priority': 50  # Default priority for hardcoded patterns
                }
                return (suggestion, metadata)

        # Generic hints for unmatched errors
        if "grad_fn" in traceback_text:
            suggestion = get_suggestion(ERROR_KEYS["AUTOGRAD"])
            metadata = {
                'matched_pattern_id': 'autograd_generic',
                'category': 'framework',
                'priority': 30
            }
            return (suggestion, metadata)

        return (None, None)
    
    @staticmethod
    def is_complete_traceback(text: str) -> bool:
        """
        Check if the text contains a complete Python traceback.

        A complete traceback starts with "Traceback (most recent call last):"
        and ends with an Exception/Error line.

        Args:
            text: The text to check.

        Returns:
            True if a complete traceback is detected.
        """
        # For standard Python tracebacks
        if "Traceback (most recent call last):" in text:
            # Check for standard Python error/exception ending
            # Pattern: ErrorType: message (at the end of a line, not indented)
            error_pattern = r'\n([A-Z][a-zA-Z0-9]*(?:Error|Exception|Warning|Interrupt)):.*'
            has_python_error = bool(re.search(error_pattern, text))
            if has_python_error:
                return True

        # For ComfyUI Validation Errors - check if we've reached a completion marker
        if "Failed to validate prompt for output" in text:
            # Validation errors end with "Executing prompt:" or continue with another "Failed to validate"
            # Count how many validation errors we have vs how many completion markers
            validation_count = text.count("Failed to validate prompt for output")
            executing_marker = "Executing prompt:" in text

            # If we see "Executing prompt:", the validation error block is complete
            if executing_marker:
                return True

            # If we have validation errors with details, consider complete when we have at least one
            # with details (* or -) and no new validation error is starting
            has_details = bool(re.search(r'\n[*\-] ', text))
            if has_details and validation_count >= 1:
                # Check if the last line looks like a conclusion (not a new error starting)
                lines = text.strip().split('\n')
                if lines:
                    last_line = lines[-1].strip()
                    # Complete if last line is "Output will be ignored" or similar
                    if "Output will be ignored" in last_line or "Prompt executed" in last_line:
                        return True

        return False

    @staticmethod
    def reload_patterns() -> bool:
        """
        Reload patterns from JSON files if they have changed.

        Useful for hot-reload during development or runtime pattern updates.

        Returns:
            True if patterns were reloaded, False otherwise
        """
        try:
            loader = get_pattern_loader()
            return loader.reload_if_changed()
        except Exception as e:
            logging.warning(f"[ErrorAnalyzer] Failed to reload patterns: {e}")
            return False

