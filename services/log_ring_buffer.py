"""
R14 Service: Log Ring Buffer.
Bounded ring buffer for capturing recent execution logs.

Features:
- O(1) append with bounded memory
- Sanitization at retrieval (not at capture)
- Thread-safe with lock-free deque

Usage:
    from services.log_ring_buffer import get_ring_buffer
    
    # Add lines (called from logger.py)
    buffer = get_ring_buffer()
    buffer.add_line("Processing node KSampler...")
    
    # Retrieve recent lines (called from collect_error_context)
    recent_logs = buffer.get_recent(50)
"""

import logging
from collections import deque
from typing import List, Optional, Callable
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class RingBufferConfig:
    """Configuration for the log ring buffer."""
    max_lines: int = 1000  # Maximum lines to keep
    sanitize_on_retrieval: bool = True  # Apply S6 sanitization
    filter_noise: bool = True  # Filter DEBUG/VERBOSE lines

# ═══════════════════════════════════════════════════════════════════════════
# LOG RING BUFFER
# ═══════════════════════════════════════════════════════════════════════════

class LogRingBuffer:
    """
    Bounded ring buffer for recent log lines.
    
    Uses deque(maxlen=N) for O(1) append and automatic eviction.
    Thread-safe for single-writer scenarios (GIL protection).
    """
    
    def __init__(self, config: Optional[RingBufferConfig] = None):
        """
        Initialize ring buffer.
        
        Args:
            config: Buffer configuration. Uses defaults if not provided.
        """
        self.config = config or RingBufferConfig()
        self._buffer: deque = deque(maxlen=self.config.max_lines)
        self._sanitizer: Optional[Callable[[str], str]] = None
        
        # Try to load sanitizer lazily
        self._load_sanitizer()
    
    def _load_sanitizer(self) -> None:
        """Lazy load S6 sanitizer to avoid circular imports."""
        try:
            # Use the convenience function that returns str, not SanitizationResult
            from sanitizer import sanitize_for_llm
            self._sanitizer = sanitize_for_llm
        except ImportError:
            # Sanitizer not available, will return raw lines
            pass
    
    def add_line(self, line: str) -> None:
        """
        Add a log line to the buffer.
        
        Args:
            line: Raw log line (not sanitized yet)
        """
        if not line:
            return
        
        # Optional noise filtering
        if self.config.filter_noise:
            line_lower = line.lower()
            # Skip very verbose lines
            if any(skip in line_lower for skip in ['debug:', '[trace]', 'verbose:']):
                return
        
        self._buffer.append(line)
    
    def get_recent(self, n: int = 50, sanitize: Optional[bool] = None) -> List[str]:
        """
        Get the most recent N log lines.
        
        Args:
            n: Number of lines to retrieve
            sanitize: Override config.sanitize_on_retrieval
            
        Returns:
            List of log lines (newest last)
        """
        should_sanitize = sanitize if sanitize is not None else self.config.sanitize_on_retrieval
        
        # Get last N items
        recent = list(self._buffer)[-n:]
        
        if should_sanitize and self._sanitizer:
            return [self._sanitizer(line) for line in recent]
        
        return recent
    
    def get_around_error(self, error_pattern: str, window: int = 25) -> List[str]:
        """
        Get log lines around a specific error pattern.
        
        Args:
            error_pattern: Pattern to search for
            window: Number of lines before/after to include
            
        Returns:
            List of log lines centered on the pattern
        """
        all_lines = list(self._buffer)
        
        # Find the pattern
        pattern_idx = None
        for i, line in enumerate(all_lines):
            if error_pattern.lower() in line.lower():
                pattern_idx = i
                break
        
        if pattern_idx is None:
            return self.get_recent(window * 2)
        
        # Get window around pattern
        start = max(0, pattern_idx - window)
        end = min(len(all_lines), pattern_idx + window + 1)
        
        result = all_lines[start:end]
        
        if self.config.sanitize_on_retrieval and self._sanitizer:
            return [self._sanitizer(line) for line in result]
        
        return result
    
    def clear(self) -> None:
        """Clear all buffered lines."""
        self._buffer.clear()
    
    def __len__(self) -> int:
        """Return current buffer size."""
        return len(self._buffer)
    
    @property
    def is_empty(self) -> bool:
        """Check if buffer is empty."""
        return len(self._buffer) == 0


# ═══════════════════════════════════════════════════════════════════════════
# GLOBAL INSTANCE
# ═══════════════════════════════════════════════════════════════════════════

# Global ring buffer instance (singleton pattern)
_ring_buffer: Optional[LogRingBuffer] = None


def get_ring_buffer(config: Optional[RingBufferConfig] = None) -> LogRingBuffer:
    """
    Get or create the global ring buffer instance.
    
    Args:
        config: Configuration for new instance (ignored if already created)
        
    Returns:
        The global LogRingBuffer instance
    """
    global _ring_buffer
    
    if _ring_buffer is None:
        _ring_buffer = LogRingBuffer(config)
    
    return _ring_buffer


def reset_ring_buffer() -> None:
    """Reset the global ring buffer (for testing)."""
    global _ring_buffer
    _ring_buffer = None
