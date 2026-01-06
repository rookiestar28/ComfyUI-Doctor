"""
Example Plugin for ComfyUI-Doctor.
Matches a specific "Example Error" for demonstration purposes.
"""
from typing import Optional, Tuple, Dict, Any

# Define a matcher function
# Input: traceback string
# Output: Tuple(suggestion, metadata) or None
def match_example_error(traceback: str) -> Optional[Tuple[str, Dict[str, Any]]]:
    if "ValueError: Example Error for Plugin" in traceback:
        suggestion = "This is an example error caught by a community plugin."
        metadata = {
            "matched_pattern_id": "EXAMPLE_PLUGIN_ERROR",
            "category": "plugin_example",
            "priority": 100
        }
        return suggestion, metadata
    return None

# Entry Point: register_matchers
# Must return a matcher function (Callable[[str], Optional[Tuple]])
def register_matchers(traceback: str) -> Optional[Tuple[str, Dict[str, Any]]]:
    """
    Plugin entry point.
    Returns the result of the matcher logic.
    Note: The pipeline calls this function directly with the traceback.
    So this function IS the matcher, or it delegates to one.
    Here we delegate.
    """
    return match_example_error(traceback)
