"""
History Store for ComfyUI-Doctor.

Provides persistent storage for error analysis history using JSON files.
Supports cross-restart history retrieval and automatic cleanup.
"""

import json
import os
import threading
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any
from datetime import datetime


@dataclass
class HistoryEntry:
    """
    Represents a single error analysis history entry.
    
    Attributes:
        timestamp: ISO format timestamp of when the error occurred
        error: The error message/traceback
        suggestion: Analysis suggestion dictionary with keys like 'pattern', 'message', 'actions'
        node_context: Optional node context dictionary
        workflow_snapshot: Optional workflow JSON snapshot (for F3)
        matched_pattern_id: Optional pattern ID that matched this error (for F4 statistics)
        pattern_category: Optional category of the matched pattern (for F4 statistics)
        pattern_priority: Optional priority of the matched pattern (for F4 statistics)
        resolution_status: Resolution status of the error (for F4 tracking)
    """
    timestamp: str
    error: str
    suggestion: Dict[str, Any]
    node_context: Optional[Dict[str, Any]] = None
    workflow_snapshot: Optional[str] = None
    # F4: Pattern metadata for statistics tracking
    matched_pattern_id: Optional[str] = None
    pattern_category: Optional[str] = None
    pattern_priority: Optional[int] = None
    resolution_status: str = "unresolved"  # "resolved"|"unresolved"|"ignored"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert entry to dictionary for JSON serialization."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "HistoryEntry":
        """Create entry from dictionary (backward compatible with old format)."""
        return cls(
            timestamp=data.get("timestamp", ""),
            error=data.get("error", ""),
            suggestion=data.get("suggestion", {}),
            node_context=data.get("node_context"),
            workflow_snapshot=data.get("workflow_snapshot"),
            # F4: Pattern metadata (optional for backward compatibility)
            matched_pattern_id=data.get("matched_pattern_id"),
            pattern_category=data.get("pattern_category"),
            pattern_priority=data.get("pattern_priority"),
            resolution_status=data.get("resolution_status", "unresolved")
        )


class HistoryStore:
    """
    Persistent storage for error analysis history.
    
    Features:
    - JSON file persistence
    - Thread-safe operations
    - Automatic size limiting (maxlen)
    - Cross-restart history retrieval
    
    Usage:
        store = HistoryStore("/path/to/history.json", maxlen=50)
        store.append(HistoryEntry(...))
        history = store.get_all()
    """
    
    def __init__(self, filepath: str, maxlen: int = 50):
        """
        Initialize the history store.
        
        Args:
            filepath: Path to the JSON file for persistence
            maxlen: Maximum number of entries to keep (oldest are removed)
        """
        self._filepath = filepath
        self._maxlen = maxlen
        self._lock = threading.Lock()
        self._history: List[HistoryEntry] = []
        self._loaded = False
    
    @property
    def filepath(self) -> str:
        """Get the history file path."""
        return self._filepath
    
    def _load(self) -> None:
        """Load history from JSON file."""
        if self._loaded:
            return
        
        try:
            if os.path.exists(self._filepath):
                with open(self._filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        self._history = [
                            HistoryEntry.from_dict(entry) 
                            for entry in data 
                            if isinstance(entry, dict)
                        ]
                        # Trim to maxlen
                        if len(self._history) > self._maxlen:
                            self._history = self._history[-self._maxlen:]
        except (json.JSONDecodeError, OSError, TypeError) as e:
            print(f"[ComfyUI-Doctor] Warning: Could not load history file: {e}")
            self._history = []
        
        self._loaded = True
    
    def _save(self) -> None:
        """Save history to JSON file."""
        try:
            # Ensure directory exists
            dir_path = os.path.dirname(self._filepath)
            if dir_path and not os.path.exists(dir_path):
                os.makedirs(dir_path, exist_ok=True)
            
            with open(self._filepath, "w", encoding="utf-8") as f:
                json.dump(
                    [entry.to_dict() for entry in self._history],
                    f,
                    ensure_ascii=False,
                    indent=2
                )
        except OSError as e:
            print(f"[ComfyUI-Doctor] Warning: Could not save history file: {e}")
    
    def append(self, entry: HistoryEntry) -> None:
        """
        Append a new entry to history.
        
        Thread-safe. Automatically persists to disk.
        Old entries are removed if maxlen is exceeded.
        
        Args:
            entry: The HistoryEntry to append
        """
        with self._lock:
            self._load()
            self._history.append(entry)
            
            # Trim to maxlen
            if len(self._history) > self._maxlen:
                self._history = self._history[-self._maxlen:]
            
            self._save()
    
    def get_all(self) -> List[Dict[str, Any]]:
        """
        Get all history entries as dictionaries.
        
        Returns entries in reverse chronological order (newest first).
        
        Returns:
            List of entry dictionaries
        """
        with self._lock:
            self._load()
            # Return in reverse order (newest first)
            return [entry.to_dict() for entry in reversed(self._history)]
    
    def get_latest(self) -> Optional[Dict[str, Any]]:
        """
        Get the most recent history entry.
        
        Returns:
            The latest entry dictionary, or None if history is empty
        """
        with self._lock:
            self._load()
            if self._history:
                return self._history[-1].to_dict()
            return None
    
    def clear(self) -> None:
        """
        Clear all history entries.
        
        Also clears the persisted file.
        """
        with self._lock:
            self._history = []
            self._save()
    
    def __len__(self) -> int:
        """Return the number of entries in history."""
        with self._lock:
            self._load()
            return len(self._history)
    
    def reload(self) -> None:
        """Force reload from disk."""
        with self._lock:
            self._loaded = False
            self._load()
