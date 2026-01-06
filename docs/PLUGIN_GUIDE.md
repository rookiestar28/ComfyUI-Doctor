# ComfyUI-Doctor Plugin Guide

ComfyUI-Doctor supports community plugins to extend error analysis capabilities beyond regex patterns. Plugins are Python scripts that can implement complex logic (e.g., checking file headers, parsing specific log formats).

## How to Create a Plugin

1. Create a Python file in `pipeline/plugins/community/` (e.g., `my_check.py`).
2. Define a function `register_matchers(traceback: str)`.
3. Implement your logic.
4. Return `(suggestion, metadata)` tuple on match, or `None`.

### Example

```python
from typing import Optional, Tuple, Dict, Any

def register_matchers(traceback: str) -> Optional[Tuple[str, Dict[str, Any]]]:
    if "My Specific Error" in traceback:
        return (
            "Try adjusting the X parameter.",
            {
                "matched_pattern_id": "MY_SPECIFIC_ERROR",
                "category": "custom",
                "priority": 90
            }
        )
    return None
```

## Security Warning

> [!WARNING]
> Plugins are executed as arbitrary Python code.
> Only install plugins from trusted sources.
> Malicious plugins can access your file system and network.

## Testing

You can test your plugin by triggering the error in ComfyUI or adding a unit test in `tests/`.
