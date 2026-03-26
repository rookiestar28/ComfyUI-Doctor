"""Shared timezone-aware UTC helpers for runtime persistence and comparisons."""

from datetime import datetime, timezone
from typing import Optional

UTC = timezone.utc
UTC_MIN = datetime.min.replace(tzinfo=UTC)


def ensure_utc(value: datetime) -> datetime:
    """Normalize a datetime to timezone-aware UTC.

    IMPORTANT: legacy persisted timestamps in Doctor were historically naive UTC.
    Treating naive values as UTC preserves backward compatibility across upgrades.
    """
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)



def utc_now() -> datetime:
    """Return the current timezone-aware UTC datetime."""
    return datetime.now(UTC)



def utc_isoformat(value: Optional[datetime] = None) -> str:
    """Serialize a datetime as ISO-8601 UTC with a trailing `Z`."""
    normalized = ensure_utc(value or utc_now())
    return normalized.isoformat().replace("+00:00", "Z")



def utc_filename_timestamp(value: Optional[datetime] = None) -> str:
    """Stable UTC timestamp for backup/migration filenames."""
    return ensure_utc(value or utc_now()).strftime("%Y%m%d-%H%M%S")



def parse_utc_timestamp(value: Optional[str]) -> Optional[datetime]:
    """Parse legacy/new persisted timestamps into aware UTC datetimes."""
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, TypeError, AttributeError):
        return None
    return ensure_utc(parsed)
