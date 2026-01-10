"""
Telemetry module for ComfyUI-Doctor.

Provides opt-in anonymous usage data collection with local-only storage (Phase 1-3).
All data is stored locally; no network upload in Phase 1-3.

Features:
- TelemetryStore: Thread-safe event buffer with atomic file writes
- RateLimiter: Token bucket algorithm (60 events/minute)
- Event validation: Allowlist-based category/action/label validation
- PII detection: Blacklist scan for sensitive patterns
"""

import json
import os
import re
import threading
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Set, Tuple, Any


# ═══════════════════════════════════════════════════════════════════════════
# CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════

SCHEMA_VERSION = "1.0"
MAX_EVENTS = 500
MAX_LABEL_LENGTH = 64
MAX_VALUE = 10000
EVENT_TTL_DAYS = 7

# Allowlist for category → actions
ALLOWED_EVENTS: Dict[str, List[str]] = {
    "feature": ["tab_switch"],
    "analysis": ["pattern_matched", "llm_called"],
    "resolution": ["marked"],
    "session": ["start", "end"],
}

# Allowlist for labels per category/action
ALLOWED_LABELS: Dict[str, Dict[str, List[str]]] = {
    "feature": {
        "tab_switch": ["chat", "stats", "settings"],
    },
    "analysis": {
        "pattern_matched": [],  # Dynamic: loaded from PatternLoader
        "llm_called": [
            "openai", "deepseek", "anthropic", "ollama", 
            "lmstudio", "gemini", "groq", "openrouter", "xai", "custom"
        ],
    },
    "resolution": {
        "marked": ["resolved", "unresolved", "ignored"],
    },
    "session": {
        "start": [],
        "end": [],
    },
}

# PII detection patterns (blacklist)
PII_PATTERNS = [
    re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'),  # Email
    re.compile(r'[A-Za-z]:\\Users\\[^\\]+'),  # Windows user path
    re.compile(r'/home/[^/]+'),  # Linux home
    re.compile(r'/Users/[^/]+'),  # macOS home
    re.compile(r'sk-[a-zA-Z0-9]{20,}'),  # API key pattern
]


# ═══════════════════════════════════════════════════════════════════════════
# DATA CLASSES
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class TelemetryEvent:
    """Represents a single telemetry event."""
    schema_version: str
    event_id: str
    timestamp: str
    category: str
    action: str
    label: Optional[str] = None
    value: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = {
            "schema_version": self.schema_version,
            "event_id": self.event_id,
            "timestamp": self.timestamp,
            "category": self.category,
            "action": self.action,
        }
        if self.label is not None:
            result["label"] = self.label
        if self.value is not None:
            result["value"] = self.value
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TelemetryEvent":
        """Create from dictionary."""
        return cls(
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            event_id=data.get("event_id", ""),
            timestamp=data.get("timestamp", ""),
            category=data.get("category", ""),
            action=data.get("action", ""),
            label=data.get("label"),
            value=data.get("value"),
        )


# ═══════════════════════════════════════════════════════════════════════════
# RATE LIMITER
# ═══════════════════════════════════════════════════════════════════════════

# R7: Import shared RateLimiter from rate_limiter.py (avoid code duplication)
from rate_limiter import RateLimiter


# ═══════════════════════════════════════════════════════════════════════════
# PATTERN ALLOWLIST
# ═══════════════════════════════════════════════════════════════════════════

_pattern_cache: Optional[Set[str]] = None
_pattern_cache_time: float = 0
PATTERN_CACHE_TTL = 300  # 5 minutes

def get_pattern_allowlist() -> Set[str]:
    """Get the current set of valid pattern IDs from PatternLoader."""
    global _pattern_cache, _pattern_cache_time
    
    now = time.time()
    if _pattern_cache is not None and (now - _pattern_cache_time) < PATTERN_CACHE_TTL:
        return _pattern_cache
    
    try:
        from pattern_loader import PatternLoader
        loader = PatternLoader()
        patterns = loader.get_all_patterns()
        _pattern_cache = {p.get("id", "") for p in patterns if p.get("id")}
        _pattern_cache_time = now
        return _pattern_cache
    except Exception:
        # If PatternLoader fails, return empty set (all patterns → __unknown__)
        return set()


def validate_pattern_label(label: str) -> str:
    """Validate pattern ID, return __unknown__ if not in allowlist."""
    if not label:
        return "__unknown__"
    allowlist = get_pattern_allowlist()
    if label in allowlist:
        return label
    return "__unknown__"


# ═══════════════════════════════════════════════════════════════════════════
# VALIDATION
# ═══════════════════════════════════════════════════════════════════════════

def contains_pii(text: str) -> bool:
    """Check if text contains PII patterns."""
    if not text:
        return False
    for pattern in PII_PATTERNS:
        if pattern.search(text):
            return True
    return False


def validate_event(data: Dict[str, Any]) -> Tuple[bool, str, Optional[TelemetryEvent]]:
    """
    Validate event data against schema and allowlists.
    
    Returns:
        (is_valid, error_message, event_or_none)
    """
    # 1. Required fields
    category = data.get("category")
    action = data.get("action")
    
    if not category or not action:
        return False, "Missing required field: category or action", None
    
    # 2. Category allowlist
    if category not in ALLOWED_EVENTS:
        return False, f"Invalid category: {category}", None
    
    # 3. Action allowlist
    if action not in ALLOWED_EVENTS[category]:
        return False, f"Invalid action: {action} for category {category}", None
    
    # 4. Label validation
    label = data.get("label")
    if label is not None:
        # Check length
        if len(label) > MAX_LABEL_LENGTH:
            return False, f"Label too long: {len(label)} > {MAX_LABEL_LENGTH}", None
        
        # Check PII
        if contains_pii(label):
            return False, "Label contains PII pattern", None
        
        # Check allowlist
        allowed_labels = ALLOWED_LABELS.get(category, {}).get(action, [])
        if allowed_labels:  # Static allowlist exists
            if label not in allowed_labels:
                return False, f"Invalid label: {label}", None
        elif category == "analysis" and action == "pattern_matched":
            # Dynamic pattern validation
            label = validate_pattern_label(label)
    
    # 5. Value validation
    value = data.get("value")
    if value is not None:
        if not isinstance(value, int):
            return False, "Value must be integer", None
        if value < 0 or value > MAX_VALUE:
            return False, f"Value out of range: {value}", None
    
    # Create event
    event = TelemetryEvent(
        schema_version=SCHEMA_VERSION,
        event_id=str(uuid.uuid4()),
        timestamp=datetime.utcnow().isoformat() + "Z",
        category=category,
        action=action,
        label=label,
        value=value,
    )
    
    return True, "", event


# ═══════════════════════════════════════════════════════════════════════════
# TELEMETRY STORE
# ═══════════════════════════════════════════════════════════════════════════

def get_doctor_data_dir() -> str:
    """Get the Doctor data directory (cross-platform)."""
    extension_root = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(extension_root, "data")
    os.makedirs(data_dir, exist_ok=True)
    return data_dir


def get_telemetry_path() -> str:
    """Get telemetry file path."""
    return os.path.join(get_doctor_data_dir(), "telemetry.json")


class TelemetryStore:
    """
    Thread-safe telemetry event storage with atomic file writes.
    
    Features:
    - Max 500 events buffer
    - 7-day TTL auto-purge
    - Atomic write via temp file + rename
    - Single-writer lock
    """
    
    def __init__(self, filepath: Optional[str] = None, enabled: bool = False):
        """
        Initialize telemetry store.
        
        Args:
            filepath: Path to telemetry JSON file (default: auto-detect)
            enabled: Whether telemetry is enabled
        """
        self._filepath = filepath or get_telemetry_path()
        self._enabled = enabled
        self._lock = threading.Lock()
        self._buffer: List[TelemetryEvent] = []
        self._loaded = False
        self._rate_limiter = RateLimiter(max_per_minute=60)
    
    @property
    def enabled(self) -> bool:
        """Check if telemetry is enabled."""
        return self._enabled
    
    @enabled.setter
    def enabled(self, value: bool) -> None:
        """Set telemetry enabled state."""
        self._enabled = value
    
    @property
    def filepath(self) -> str:
        """Get the telemetry file path."""
        return self._filepath
    
    def _load(self) -> None:
        """Load events from file (internal, called with lock held)."""
        if self._loaded:
            return
        
        try:
            if os.path.exists(self._filepath):
                with open(self._filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        self._buffer = [
                            TelemetryEvent.from_dict(e)
                            for e in data
                            if isinstance(e, dict)
                        ]
        except (json.JSONDecodeError, OSError) as e:
            print(f"[ComfyUI-Doctor] Telemetry load warning: {e}")
            self._buffer = []
        
        self._loaded = True
    
    def _save_atomic(self) -> None:
        """Save events atomically via temp file + rename."""
        try:
            # Ensure directory exists
            dir_path = os.path.dirname(self._filepath)
            if dir_path and not os.path.exists(dir_path):
                os.makedirs(dir_path, exist_ok=True)
            
            # Write to temp file
            temp_path = self._filepath + ".tmp"
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(
                    [e.to_dict() for e in self._buffer],
                    f,
                    ensure_ascii=False,
                    indent=2,
                )
            
            # Atomic rename
            os.replace(temp_path, self._filepath)
        except OSError as e:
            print(f"[ComfyUI-Doctor] Telemetry save warning: {e}")
    
    def _purge_old_events(self) -> None:
        """Remove events older than TTL."""
        cutoff = datetime.utcnow() - timedelta(days=EVENT_TTL_DAYS)
        cutoff_str = cutoff.isoformat() + "Z"
        self._buffer = [e for e in self._buffer if e.timestamp >= cutoff_str]
    
    def _enforce_limit(self) -> None:
        """Enforce max events limit (remove oldest)."""
        if len(self._buffer) > MAX_EVENTS:
            self._buffer = self._buffer[-MAX_EVENTS:]
    
    def track(self, data: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Record a telemetry event.
        
        Args:
            data: Event data (category, action, label?, value?)
        
        Returns:
            (success, message)
        """
        # Check if enabled
        if not self._enabled:
            return False, "Telemetry disabled"
        
        # Rate limit
        if not self._rate_limiter.allow():
            return False, "Rate limited"
        
        # Validate
        is_valid, error_msg, event = validate_event(data)
        if not is_valid or event is None:
            return False, error_msg
        
        # Store
        with self._lock:
            self._load()
            self._buffer.append(event)
            self._purge_old_events()
            self._enforce_limit()
            self._save_atomic()
        
        return True, "Event recorded"
    
    def get_buffer(self) -> List[Dict[str, Any]]:
        """Get all buffered events as dictionaries."""
        with self._lock:
            self._load()
            return [e.to_dict() for e in self._buffer]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get buffer statistics."""
        with self._lock:
            self._load()
            if not self._buffer:
                return {
                    "count": 0,
                    "oldest": None,
                    "newest": None,
                }
            return {
                "count": len(self._buffer),
                "oldest": self._buffer[0].timestamp if self._buffer else None,
                "newest": self._buffer[-1].timestamp if self._buffer else None,
            }
    
    def clear(self) -> None:
        """Clear all buffered events."""
        with self._lock:
            self._buffer = []
            self._save_atomic()
    
    def export_json(self) -> str:
        """Export buffer as JSON string."""
        with self._lock:
            self._load()
            return json.dumps(
                [e.to_dict() for e in self._buffer],
                ensure_ascii=False,
                indent=2,
            )
    
    def __len__(self) -> int:
        """Return buffer size."""
        with self._lock:
            self._load()
            return len(self._buffer)


# ═══════════════════════════════════════════════════════════════════════════
# SINGLETON INSTANCE
# ═══════════════════════════════════════════════════════════════════════════

# Global telemetry store instance (disabled by default)
_telemetry_store: Optional[TelemetryStore] = None


def get_telemetry_store() -> TelemetryStore:
    """Get the global telemetry store instance."""
    global _telemetry_store
    if _telemetry_store is None:
        _telemetry_store = TelemetryStore(enabled=False)
    return _telemetry_store


def track_event(category: str, action: str, label: Optional[str] = None, value: Optional[int] = None) -> bool:
    """
    Convenience function to track a telemetry event.
    
    Args:
        category: Event category (feature, analysis, resolution, session)
        action: Event action
        label: Optional label
        value: Optional numeric value
    
    Returns:
        True if event was recorded, False otherwise
    """
    store = get_telemetry_store()
    success, _ = store.track({
        "category": category,
        "action": action,
        "label": label,
        "value": value,
    })
    return success
