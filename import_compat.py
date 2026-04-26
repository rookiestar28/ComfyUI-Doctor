"""Import fallback helpers for package and standalone execution modes."""

from __future__ import annotations


_STANDALONE_RELATIVE_IMPORT_MARKERS = (
    "attempted relative import with no known parent package",
    "attempted relative import beyond top-level package",
)


def ensure_absolute_import_fallback_allowed(error: ImportError) -> None:
    """Re-raise unexpected ImportError instead of hiding broken internal imports."""
    message = str(error)
    if any(marker in message for marker in _STANDALONE_RELATIVE_IMPORT_MARKERS):
        return
    raise error
