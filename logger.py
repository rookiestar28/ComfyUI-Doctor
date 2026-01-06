"""
Smart Logger for ComfyUI Runtime Diagnostics.
Intercepts stdout/stderr to capture logs and provide real-time error analysis.

ARCHITECTURE (v1.3.0):
- SafeStreamWrapper: Wraps sys.stdout/stderr (after ComfyUI's LogInterceptor if present)
- DoctorLogProcessor: Background thread that processes queued messages
- Zero deadlock risk: write() holds no locks, only enqueues messages

Previous issues (v1.2.x):
- Used SmartLogger with AsyncFileWriter
- Attempted to use ComfyUI's on_flush callbacks (failed due to callback ordering)
- Had potential deadlock risks with nested stream wrapping

See: .planning/STAGE1_LOGGER_FIX_PLAN.md for full design details
"""

import sys
import datetime
import threading
import queue
import time
import os
import logging
from collections import deque
from typing import Optional, Dict, Any, List
try:
    from .analyzer import ErrorAnalyzer
    from .config import CONFIG
    from .history_store import HistoryStore, HistoryEntry
except ImportError:
    # Fallback for direct execution (tests)
    from analyzer import ErrorAnalyzer
    from config import CONFIG
    from history_store import HistoryStore, HistoryEntry


# ==============================================================================
# Global State for API Access
# ==============================================================================

_last_analysis: Dict[str, Any] = {
    "error": None,
    "suggestion": None,
    "timestamp": None,
    "node_context": None,  # NodeContext.to_dict() result
}

# P1: Error history buffer (ring buffer for last N errors)
_analysis_history: deque = deque(maxlen=CONFIG.history_size)

# F1: Persistent history store
_current_dir = os.path.dirname(os.path.abspath(__file__))
_history_file = os.path.join(_current_dir, "logs", "error_history.json")
_history_store: Optional[HistoryStore] = None

def _get_history_store() -> HistoryStore:
    """Lazy initialization of history store."""
    global _history_store
    if _history_store is None:
        _history_store = HistoryStore(_history_file, maxlen=CONFIG.history_size)
    return _history_store

# R2: Thread safety locks for shared mutable state
_history_lock = threading.Lock()


# ==============================================================================
# API Functions (preserved from original implementation)
# ==============================================================================

def get_last_analysis() -> Dict[str, Any]:
    """Get the last error analysis result for API access."""
    with _history_lock:
        return _last_analysis.copy()


def get_analysis_history() -> List[Dict[str, Any]]:
    """Get the error analysis history (most recent first)."""
    # Prefer persistent store, fallback to in-memory
    try:
        store = _get_history_store()
        history = store.get_all()
        if history:
            return history
    except Exception:
        pass  # Fallback to in-memory

    with _history_lock:
        return list(reversed(_analysis_history))


def clear_analysis_history() -> bool:
    """Clear all history (both persistent and in-memory)."""
    try:
        store = _get_history_store()
        store.clear()
        with _history_lock:
            _analysis_history.clear()
        return True
    except Exception:
        return False


# ==============================================================================
# New Architecture: SafeStreamWrapper + DoctorLogProcessor
# ==============================================================================

class SafeStreamWrapper:
    """
    Safe stream wrapper that avoids deadlock with ComfyUI's LogInterceptor.

    Design principles:
    1. write() immediately pass-through (holds NO locks)
    2. Message is enqueued for background processing
    3. All other attributes are proxied to original stream

    This avoids conflicts with ComfyUI's LogInterceptor because:
    - We don't hold any locks during write()
    - We call original_stream.write() FIRST, then enqueue
    - Background thread is completely decoupled
    """

    def __init__(self, original_stream, message_queue):
        """
        Initialize wrapper.

        Args:
            original_stream: Original stream (may be LogInterceptor or raw stdout/stderr)
            message_queue: Queue for background processing
        """
        self._original_stream = original_stream
        self._queue = message_queue

    def write(self, data):
        """
        Write data: immediate pass-through + enqueue for analysis.

        CRITICAL: This method holds NO locks to avoid deadlock.
        """
        # 1. Immediately write to original stream (may be LogInterceptor)
        try:
            self._original_stream.write(data)
        except (OSError, AttributeError):
            pass  # Stream may be closed during shutdown

        # 2. Enqueue for background processing (non-blocking)
        try:
            self._queue.put_nowait(data)
        except queue.Full:
            # Queue full: discard message (extreme case, avoid blocking)
            pass

    def flush(self):
        """Flush original stream."""
        try:
            self._original_stream.flush()
        except (OSError, AttributeError):
            pass

    def __getattr__(self, name):
        """Proxy all other attributes to original stream (encoding, isatty, fileno, etc)."""
        return getattr(self._original_stream, name)


class DoctorLogProcessor(threading.Thread):
    """
    Background thread for log analysis.

    Functionality:
    1. Read messages from queue
    2. Assemble traceback buffer (same logic as old SmartLogger._analyze_stream)
    3. Call ErrorAnalyzer.analyze()
    4. Update history store

    This runs completely independently from the main thread.
    """

    def __init__(self, message_queue):
        super().__init__(daemon=True, name="DoctorLogProcessor")
        self._queue = message_queue
        self._running = True

        # Traceback buffer state (migrated from SmartLogger)
        self.buffer = []
        self.in_traceback = False
        self.last_buffer_time = 0

    def run(self):
        """Main loop: process queued messages."""
        while self._running:
            try:
                # Use timeout to allow periodic buffer timeout checks
                message = self._queue.get(timeout=0.5)
                self._process_message(message)

            except queue.Empty:
                # Timeout: check if buffer needs flushing
                self._check_buffer_timeout()

            except Exception as e:
                # Log error but don't crash the thread
                logging.error(f"[Doctor] LogProcessor error: {e}", exc_info=True)

    def _process_message(self, message):
        """
        Process a single message (migrated from SmartLogger._analyze_stream).
        """
        current_time = time.time()

        # P3: Urgent single-line warnings (immediate analysis)
        if "❌ CRITICAL" in message or "⚠️ Meta Tensor" in message:
            result = ErrorAnalyzer.analyze(message)
            suggestion, metadata = result if result else (None, None)
            if suggestion:
                self._record_analysis(message, suggestion, metadata)
            return

        # Detect traceback start
        if "Traceback (most recent call last):" in message:
            self.in_traceback = True
            self.buffer = [message]
            self.last_buffer_time = current_time
            return

        # Handle validation errors
        if "Failed to validate prompt for output" in message:
            if not self.in_traceback:
                self.in_traceback = True
                self.buffer = [message]
                self.last_buffer_time = current_time
            else:
                self.buffer.append(message)
                self.last_buffer_time = current_time
            return

        if self.in_traceback:
            # Check timeout
            if current_time - self.last_buffer_time > CONFIG.traceback_timeout_seconds:
                full_traceback = "".join(self.buffer)
                result = ErrorAnalyzer.analyze(full_traceback)
                suggestion, metadata = result if result else (None, None)
                if suggestion or "Failed to validate" in full_traceback:
                    self._record_analysis(full_traceback, suggestion, metadata)
                self.in_traceback = False
                self.buffer = []
            else:
                self.buffer.append(message)
                self.last_buffer_time = current_time
                full_traceback = "".join(self.buffer)

                # Validation error completion marker
                if "Failed to validate prompt for output" in full_traceback:
                    if "Executing prompt:" in message:
                        result = ErrorAnalyzer.analyze(full_traceback)
                        suggestion, metadata = result if result else (None, None)
                        self._record_analysis(full_traceback, suggestion, metadata)
                        self.in_traceback = False
                        self.buffer = []
                        return
                    return

                # Normal traceback completion
                if ErrorAnalyzer.is_complete_traceback(full_traceback):
                    result = ErrorAnalyzer.analyze(full_traceback)
                    suggestion, metadata = result if result else (None, None)
                    self._record_analysis(full_traceback, suggestion, metadata)
                    self.in_traceback = False
                    self.buffer = []

                # Buffer limit safety
                elif len(self.buffer) > CONFIG.buffer_limit:
                    self.in_traceback = False
                    self.buffer = []

    def _check_buffer_timeout(self):
        """Check if buffer has timed out (called on queue.Empty)."""
        if self.in_traceback and self.buffer:
            current_time = time.time()
            if current_time - self.last_buffer_time > CONFIG.traceback_timeout_seconds:
                full_traceback = "".join(self.buffer)
                result = ErrorAnalyzer.analyze(full_traceback)
                suggestion, metadata = result if result else (None, None)
                if suggestion or "Failed to validate" in full_traceback:
                    self._record_analysis(full_traceback, suggestion, metadata)
                self.in_traceback = False
                self.buffer = []

    def _record_analysis(self, full_traceback, suggestion, metadata=None):
        """
        Record analysis result (migrated from SmartLogger._record_analysis).

        Args:
            full_traceback: The full traceback string
            suggestion: Suggestion text (or None if no match)
            metadata: Optional metadata dict with pattern info (from F4)
        """
        node_context = ErrorAnalyzer.extract_node_context(full_traceback)
        timestamp = datetime.datetime.now().isoformat()

        new_analysis = {
            "error": full_traceback,
            "suggestion": suggestion,
            "timestamp": timestamp,
            "node_context": node_context.to_dict() if node_context else None,
        }

        # R2: Thread-safe update of shared state
        with _history_lock:
            global _last_analysis
            _last_analysis = new_analysis
            _analysis_history.append(new_analysis.copy())

        # F1: Persist to history store
        try:
            store = _get_history_store()
            entry = HistoryEntry(
                timestamp=timestamp,
                error=full_traceback,
                suggestion=suggestion if suggestion else {},
                node_context=node_context.to_dict() if node_context else None,
            )
            store.append(entry)
        except Exception:
            pass  # Persistence failure should not break error analysis

        # Only print if we have something useful (context OR suggestion)
        if not suggestion and (not node_context or not node_context.is_valid()):
            return

        # Build formatted output
        output_parts = []
        output_parts.append(f"\n{'-'*40}")

        # Add node context if available
        if node_context and node_context.is_valid():
            node_info = []
            if node_context.node_id:
                node_info.append(f"Node ID: #{node_context.node_id}")
            if node_context.node_name:
                node_info.append(f"Name: {node_context.node_name}")
            if node_context.node_class:
                node_info.append(f"Class: {node_context.node_class}")
            if node_context.custom_node_path:
                node_info.append(f"Source: {node_context.custom_node_path}")

            output_parts.append("🎯 ERROR LOCATION: " + " | ".join(node_info))

        # Add suggestion (defensive: ensure suggestion is a string)
        if suggestion:
            if isinstance(suggestion, str):
                output_parts.append(suggestion)
            elif isinstance(suggestion, (tuple, list)) and len(suggestion) > 0:
                # Handle case where suggestion is accidentally a tuple (e.g., from analyzer)
                output_parts.append(str(suggestion[0]) if suggestion[0] else "")

        output_parts.append(f"{'-'*40}\n")

        formatted_output = "\n".join(output_parts)

        # Print to stdout (will be captured by our wrapper and ComfyUI's LogInterceptor)
        try:
            print(formatted_output, file=sys.__stdout__)
        except Exception:
            pass  # Silently fail if stdout is unavailable

    def stop(self):
        """Gracefully stop the processor thread."""
        self._running = False


# ==============================================================================
# Installation API (preserved interface, new implementation)
# ==============================================================================

# Global state for installation
_message_queue = None
_log_processor = None
_original_stdout = None
_original_stderr = None


def install(log_path: str):
    """
    Install Doctor logger (new architecture).

    Args:
        log_path: Log file path (currently unused, kept for API compatibility)

    Architecture:
    - Creates message queue and background processor thread
    - Wraps sys.stdout/stderr with SafeStreamWrapper
    - Background thread handles all error analysis

    Note: This completely avoids the on_flush callback issues from v1.2.x
    """
    global _message_queue, _log_processor, _original_stdout, _original_stderr

    # Avoid duplicate installation
    if _message_queue is not None:
        logging.warning("[Doctor] Logger already installed, skipping")
        return

    # Create queue and background processor
    _message_queue = queue.Queue(maxsize=1000)
    _log_processor = DoctorLogProcessor(_message_queue)
    _log_processor.start()

    # Save original streams (may already be ComfyUI's LogInterceptor)
    _original_stdout = sys.stdout
    _original_stderr = sys.stderr

    # Wrap stdout/stderr
    sys.stdout = SafeStreamWrapper(_original_stdout, _message_queue)
    sys.stderr = SafeStreamWrapper(_original_stderr, _message_queue)

    logging.info("[Doctor] Logger installed (SafeStreamWrapper mode)")
    logging.info(f"[Doctor] Original stdout type: {type(_original_stdout).__name__}")
    logging.info(f"[Doctor] Original stderr type: {type(_original_stderr).__name__}")


def uninstall():
    """Uninstall logger and restore original streams."""
    global _log_processor, _original_stdout, _original_stderr, _message_queue

    # Restore streams
    if _original_stdout:
        sys.stdout = _original_stdout
    if _original_stderr:
        sys.stderr = _original_stderr

    # Stop background thread
    if _log_processor:
        _log_processor.stop()
        _log_processor.join(timeout=2.0)
        _log_processor = None

    # Clear queue
    _message_queue = None

    logging.info("[Doctor] Logger uninstalled")


# ==============================================================================
# Backward Compatibility
# ==============================================================================

class SmartLogger:
    """
    Backward compatibility class.

    The old SmartLogger interface is preserved for existing code that may
    reference it, but internally it now uses the new architecture.
    """

    @classmethod
    def install(cls, log_path: str):
        """Install logger (delegates to new install())."""
        install(log_path)

    @classmethod
    def uninstall(cls):
        """Uninstall logger (delegates to new uninstall())."""
        uninstall()
