"""Scalar node identity shared by diagnostic target producers."""
from typing import Any, TypeAlias

NodeId: TypeAlias = int | str
MAX_NODE_ID_LENGTH = 1024
MAX_SAFE_INTEGER = (1 << 53) - 1


def valid_node_id(value: Any) -> NodeId | None:
    """Keep the original scalar; do not turn opaque or leading-zero IDs into numbers."""
    if type(value) is int:
        return value if 0 <= value <= MAX_SAFE_INTEGER else None
    if isinstance(value, str) and 0 < len(value) <= MAX_NODE_ID_LENGTH:
        if value.strip() != value or any(
            ord(char) < 32 or ord(char) == 127 or 0xD800 <= ord(char) <= 0xDFFF
            for char in value
        ):
            return None
        return value
    return None
