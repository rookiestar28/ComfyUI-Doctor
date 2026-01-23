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
import hashlib
from collections import deque
from typing import Optional, Dict, Any, List
try:
    from .analyzer import ErrorAnalyzer
    from .config import CONFIG
    from .history_store import HistoryStore, HistoryEntry
    from services.log_ring_buffer import get_ring_buffer
    from services.context_extractor import detect_fatal_pattern
    from services import doctor_paths
except ImportError:
    # Fallback for direct execution (tests)
    from analyzer import ErrorAnalyzer
    from config import CONFIG
    from history_store import HistoryStore, HistoryEntry
    try:
        from services.log_ring_buffer import get_ring_buffer
    except ImportError:
        get_ring_buffer = None
    try:
        from services.context_extractor import detect_fatal_pattern
    except ImportError:
        detect_fatal_pattern = None
    try:
        from services import doctor_paths
    except ImportError:
        doctor_paths = None


# ==============================================================================
# Global State for API Access
# ==============================================================================

_last_analysis: Dict[str, Any] = {
    "error": None,
    "suggestion": None,
    "timestamp": None,
    "node_context": None,  # NodeContext.to_dict() result
    "analysis_metadata": None,
    "matched_pattern_id": None,
    "pattern_category": None,
    "pattern_priority": None,
    "resolution_status": None,
}

# P1: Error history buffer (ring buffer for last N errors)
# When history_size=0, use unbounded deque
_analysis_history: deque = deque() if CONFIG.history_size == 0 else deque(maxlen=CONFIG.history_size)

# F1: Persistent history store
# R18: Use canonical data directory via doctor_paths
_current_dir = os.path.dirname(os.path.abspath(__file__))

def _resolve_history_path() -> str:
    """
    Choose a writable, stable location for history persistence.

    Why:
    - ComfyUI Desktop / Manager may treat writes inside the extension folder as "conflicts"
      and may also place extensions under locations with stricter permissions.
    - Using the canonical Doctor data dir is robust across install modes
      (portable/git clone/desktop) and respects ComfyUI's user directory when available.
    """
    if doctor_paths:
        try:
            data_dir = doctor_paths.get_doctor_data_dir()
            return os.path.join(data_dir, "error_history.json")
        except Exception:
            pass
    return os.path.join(_current_dir, "logs", "error_history.json")


_history_file = _resolve_history_path()
_history_store: Optional[HistoryStore] = None

def _migrate_legacy_data():
    """R18: One-time migration of legacy history to new location."""
    if not doctor_paths:
        return

    legacy_path = os.path.join(_current_dir, "logs", "error_history.json")
    target_path = _history_file

    # If legacy exists and target doesn't, migrate.
    # Best-effort: prefer moving the file out of the extension folder to avoid "conflict" warnings.
    if os.path.exists(legacy_path) and not os.path.exists(target_path):
        try:
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            try:
                os.replace(legacy_path, target_path)
            except Exception:
                import shutil
                shutil.copy2(legacy_path, target_path)
                try:
                    os.remove(legacy_path)
                except Exception:
                    pass
        except Exception as e:
            logging.error(f"[ComfyUI-Doctor] Migration failed: {e}")

def _get_history_store() -> HistoryStore:
    """Lazy initialization of history store."""
    global _history_store
    if _history_store is None:
        _migrate_legacy_data()
        _history_store = HistoryStore(
            _history_file,
            maxlen=CONFIG.history_size,
            max_bytes=getattr(CONFIG, 'history_size_bytes', 5*1024*1024)
        )
    return _history_store

# R2: Thread safety locks for shared mutable state
_history_lock = threading.Lock()

_TRACEBACK_ACTIVE = threading.Event()


class DroppingQueue:
    """
    Bounded queue with drop policy and counters.

    - Non-priority messages are dropped when full.
    - Priority messages evict the oldest non-priority item if possible.
    - Drop counters are tracked for health/observability.
    """

    def __init__(self, maxsize: int = 1000):
        self._maxsize = maxsize
        self._queue = deque()
        self._cv = threading.Condition()
        self._stats = {
            "queue_dropped_total": 0,
            "queue_dropped_priority": 0,
            "queue_dropped_non_priority": 0,
            "queue_dropped_oldest": 0,
        }

    def _record_drop(self, item):
        if not item:
            return
        priority, _ = item
        self._stats["queue_dropped_total"] += 1
        if priority:
            self._stats["queue_dropped_priority"] += 1
        else:
            self._stats["queue_dropped_non_priority"] += 1

    def _remove_at(self, index: int):
        self._queue.rotate(-index)
        item = self._queue.popleft()
        self._queue.rotate(index)
        return item

    def _drop_oldest(self, prefer_non_priority: bool):
        if not self._queue:
            return None
        if prefer_non_priority:
            for idx, item in enumerate(self._queue):
                if not item[0]:
                    return self._remove_at(idx)
        return self._queue.popleft()

    def put_nowait(self, item, priority: bool = False) -> bool:
        with self._cv:
            if self._maxsize and len(self._queue) >= self._maxsize:
                if priority:
                    dropped = self._drop_oldest(prefer_non_priority=True)
                    self._record_drop(dropped)
                    self._stats["queue_dropped_oldest"] += 1
                else:
                    self._stats["queue_dropped_total"] += 1
                    self._stats["queue_dropped_non_priority"] += 1
                    return False

            self._queue.append((priority, item))
            self._cv.notify()
            return True

    def get(self, timeout: float = None):
        with self._cv:
            if not self._queue:
                self._cv.wait(timeout)
            if not self._queue:
                raise queue.Empty
            return self._queue.popleft()

    def qsize(self) -> int:
        with self._cv:
            return len(self._queue)

    def get_stats(self) -> Dict[str, int]:
        with self._cv:
            return dict(self._stats)

    def clear(self) -> None:
        with self._cv:
            self._queue.clear()


def _is_priority_message(message: str) -> bool:
    if _TRACEBACK_ACTIVE.is_set():
        return True
    if not message:
        return False
    if "Traceback (most recent call last):" in message:
        return True
    if "Failed to validate prompt for output" in message:
        return True
    return False



# ==============================================================================
# API Functions (preserved from original implementation)
# ==============================================================================

def get_last_analysis() -> Dict[str, Any]:
    """Get the last error analysis result for API access."""
    with _history_lock:
        return _last_analysis.copy()


def update_resolution_status(timestamp: str, status: str) -> bool:
    """Update resolution status in history store and in-memory analysis data."""
    updated = False

    try:
        store = _get_history_store()
        with store._lock:
            store._load()
            for entry in store._history:
                if entry.timestamp == timestamp:
                    entry.resolution_status = status
                    updated = True
                    break
            store._save()
    except Exception:
        pass

    with _history_lock:
        global _last_analysis
        if _last_analysis.get("timestamp") == timestamp:
            _last_analysis["resolution_status"] = status
            updated = True

        for entry in _analysis_history:
            if entry.get("timestamp") == timestamp:
                entry["resolution_status"] = status
                updated = True
                break

    return updated


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
            priority = _is_priority_message(data)
            self._queue.put_nowait(data, priority=priority)
        except Exception:
            pass
        
        # R14: Add to ring buffer for reliable log context capture
        try:
            if get_ring_buffer:
                ring_buffer = get_ring_buffer()
                ring_buffer.add_line(data)
        except Exception:
            pass  # Never fail on ring buffer operations

    def flush(self):
        """Flush original stream."""
        try:
            self._original_stream.flush()
        except (OSError, AttributeError):
            pass

    def __getattr__(self, name):
        """Proxy all other attributes to original stream (encoding, isatty, fileno, etc)."""
        return getattr(self._original_stream, name)


class FlushSafeProxy:
    """
    Stream proxy that never raises from write()/flush().

    Purpose:
    - Some ComfyUI Desktop builds use a LogInterceptor whose flush() can raise
      `OSError: [Errno 22] Invalid argument` under Windows packaging.
    - Python's logging.StreamHandler calls flush() after every emit.
    - If flush raises, logging prints an exception traceback, causing a log storm.

    This proxy keeps the original stream behavior but makes flush safe.
    It intentionally does NOT enqueue messages for Doctor analysis.
    """

    def __init__(self, original_stream):
        self._original_stream = original_stream

    def write(self, data):
        try:
            return self._original_stream.write(data)
        except (OSError, AttributeError, ValueError):
            return 0

    def flush(self):
        try:
            return self._original_stream.flush()
        except (OSError, AttributeError, ValueError):
            return None

    def __getattr__(self, name):
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
        self._metrics = {
            "buffer_dropped": 0,
            "traceback_resets": 0,
            "queue_timeouts": 0,
        }

        # Traceback buffer state (migrated from SmartLogger)
        self.buffer = []
        self.in_traceback = False
        self.last_buffer_time = 0
        self._aggregate_window_seconds = 60

    def _parse_ts(self, ts: str) -> datetime.datetime:
        try:
            if not ts:
                return datetime.datetime.min
            return datetime.datetime.fromisoformat(ts.replace("Z", "+00:00")).replace(tzinfo=None)
        except Exception:
            return datetime.datetime.min

    def run(self):
        """Main loop: process queued messages."""
        while self._running:
            try:
                # Use timeout to allow periodic buffer timeout checks
                priority, message = self._queue.get(timeout=0.5)
                self._process_message(message)

            except queue.Empty:
                # Timeout: check if buffer needs flushing
                self._metrics["queue_timeouts"] += 1
                self._check_buffer_timeout()

            except Exception as e:
                # Log error but don't crash the thread
                logging.error(f"[Doctor] LogProcessor error: {e}", exc_info=True)

    def _process_message(self, message):
        """
        Process a single message (migrated from SmartLogger._analyze_stream).
        """
        current_time = time.time()

        # Always check buffer timeout, even when logs keep coming.
        # In some environments (e.g., ComfyUI Desktop), periodic Doctor-API logs
        # can prevent queue.Empty from firing, which previously blocked buffer flush
        # for non-traceback errors like "Failed to validate prompt for output".
        self._check_buffer_timeout()

        # ═══════════════════════════════════════════════════════════════
        # CRITICAL FIX (2026-01-06): Prevent recursive log capture
        # ═══════════════════════════════════════════════════════════════
        # BUG: Doctor's own log messages (e.g., "[Doctor] _record_analysis called")
        #      were being captured by SafeStreamWrapper, and since they contain
        #      the original error text, they triggered new analysis cycles.
        #      This caused duplicate suggestions and infinite recursion.
        #
        # SOLUTION: Skip any message that contains Doctor's internal log markers.
        #
        # ⚠️ DO NOT REMOVE THIS CHECK! It prevents infinite recursion.
        # See: .planning/260106-BUGFIX_DUPLICATE_LOG_CAPTURE.md
        # ═══════════════════════════════════════════════════════════════
        doctor_markers = [
            "[Doctor]",       # Internal logging prefix
            "[Doctor-API]",   # API logging prefix
            "🎯 ERROR LOCATION:",  # Formatted output header
            "💡 SUGGESTION:",      # Formatted output suggestion
            "----------------------------------------",  # Divider line
        ]
        for marker in doctor_markers:
            if marker in message:
                return  # Skip Doctor's own output to prevent recursion

        # P3: Urgent single-line warnings (immediate analysis)
        # R14: Enhanced with detect_fatal_pattern for non-traceback errors
        is_urgent = "❌ CRITICAL" in message or "⚠️ Meta Tensor" in message
        
        # R14: Check for fatal patterns (CUDA OOM, CRITICAL, etc.)
        if not is_urgent and detect_fatal_pattern:
            fatal_marker = detect_fatal_pattern(message)
            if fatal_marker:
                is_urgent = True
                logging.debug(f"[Doctor] R14 fatal pattern detected: {fatal_marker}")
        
        if is_urgent:
            result = ErrorAnalyzer.analyze(message)
            suggestion, metadata = result if result else (None, None)
            if suggestion:
                self._record_analysis(message, suggestion, metadata)
            return

        # Detect traceback start
        if "Traceback (most recent call last):" in message:
            self._set_traceback_state(True)
            self.buffer = [message]
            self.last_buffer_time = current_time
            return

        # Handle validation errors
        if "Failed to validate prompt for output" in message:
            if not self.in_traceback:
                self._set_traceback_state(True)
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
                self._set_traceback_state(False)
                self.buffer = []
            else:
                # ═══════════════════════════════════════════════════════════════
                # CRITICAL FIX (2026-01-06): Check completion marker BEFORE buffer.append()
                # ═══════════════════════════════════════════════════════════════
                # BUG: "Prompt executed in X seconds" was being added to buffer BEFORE
                #      is_complete_traceback() detected completion, causing it to be
                #      recorded as part of the error message.
                #
                # SOLUTION: Intercept "Prompt executed" BEFORE appending to buffer.
                #           Use current buffer (without this line) for recording.
                #
                # DO NOT MOVE THIS CHECK AFTER buffer.append()!
                # ═══════════════════════════════════════════════════════════════
                if "Prompt executed" in message:
                    full_traceback = "".join(self.buffer)
                    if full_traceback.strip():  # Only record if buffer has content
                        result = ErrorAnalyzer.analyze(full_traceback)
                        suggestion, metadata = result if result else (None, None)
                        self._record_analysis(full_traceback, suggestion, metadata)
                    self._set_traceback_state(False)
                    self.buffer = []
                    return
                
                self.buffer.append(message)
                self.last_buffer_time = current_time
                full_traceback = "".join(self.buffer)

                # Normal traceback completion
                if ErrorAnalyzer.is_complete_traceback(full_traceback):
                    result = ErrorAnalyzer.analyze(full_traceback)
                    suggestion, metadata = result if result else (None, None)
                    self._record_analysis(full_traceback, suggestion, metadata)
                    self._set_traceback_state(False)
                    self.buffer = []

                # Buffer limit safety
                elif len(self.buffer) > CONFIG.buffer_limit:
                    self._metrics["buffer_dropped"] += 1
                    self._metrics["traceback_resets"] += 1
                    self._set_traceback_state(False)
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
                self._metrics["traceback_resets"] += 1
                self._set_traceback_state(False)
                self.buffer = []

    def _set_traceback_state(self, active: bool) -> None:
        self.in_traceback = active
        if active:
            _TRACEBACK_ACTIVE.set()
        else:
            _TRACEBACK_ACTIVE.clear()

    def _record_analysis(self, full_traceback, suggestion, metadata=None):
        """
        Record analysis result (migrated from SmartLogger._record_analysis).

        Args:
            full_traceback: The full traceback string
            suggestion: Suggestion text (or None if no match)
            metadata: Optional metadata dict with pattern info (from F4)
        """
        # DEBUG: Log what's being recorded
        logging.info(f"[Doctor] _record_analysis called with traceback preview: {full_traceback[:100] if full_traceback else 'None'}...")
        
        # ═══════════════════════════════════════════════════════════════
        # CRITICAL FIX (2026-01-06): Prevent non-error messages from
        # overwriting legitimate error records
        # ═══════════════════════════════════════════════════════════════
        # BUG: Normal messages like "Prompt executed in X seconds" were
        #      being recorded as errors, overwriting real error logs.
        #
        # SOLUTION: Validate that full_traceback contains actual error
        #           indicators before recording.
        #
        # DO NOT REMOVE THIS VALIDATION!
        # ═══════════════════════════════════════════════════════════════
        
        # Skip recording if no actual error content
        # This prevents normal messages like "Prompt executed in X seconds" from
        # overwriting legitimate error records
        if not full_traceback:
            return

        # Desktop-specific: ignore ComfyUI logging flush exceptions.
        # These can create high-frequency "error storms" even when inference isn't running,
        # rapidly filling error_history.json with non-actionable noise.
        if (
            "logging\\__init__.py" in full_traceback
            and "ComfyUI\\app\\logger.py" in full_traceback
            and "OSError: [Errno 22] Invalid argument" in full_traceback
        ):
            return
        
        # Explicit exclusion for normal execution messages
        # These messages should NEVER be recorded as errors
        normal_messages = [
            "Prompt executed in",
            "got prompt",
            "Executing node",
            "To see the GUI go to:",
            "Starting server",
        ]
        for normal_msg in normal_messages:
            if normal_msg in full_traceback and "Error" not in full_traceback and "Exception" not in full_traceback:
                logging.debug(f"[Doctor] Skipping normal message: {full_traceback[:100]}")
                return
        
        # Require at least one error indicator
        error_indicators = [
            "Traceback (most recent call last):",
            "Error:",
            "Error ",  # Catch RuntimeError, ValueError etc without colon
            "Exception:",
            "Exception ",
            "Failed to validate",
            "❌ CRITICAL",
            "⚠️ Meta Tensor",
        ]
        has_error_indicator = any(indicator in full_traceback for indicator in error_indicators)
        
        # Also accept if we have a valid suggestion (pattern matched)
        if not has_error_indicator and not suggestion:
            logging.debug(f"[Doctor] Skipping non-error message (no indicators): {full_traceback[:100]}")
            return
        
        analysis_metadata = metadata if isinstance(metadata, dict) else {}
        matched_pattern_id = analysis_metadata.get("matched_pattern_id")
        pattern_category = analysis_metadata.get("pattern_category") or analysis_metadata.get("category")
        pattern_priority = analysis_metadata.get("pattern_priority") or analysis_metadata.get("priority")

        node_context = ErrorAnalyzer.extract_node_context(full_traceback)
        timestamp = datetime.datetime.now().isoformat()
        error_signature = hashlib.sha256(full_traceback.encode("utf-8", errors="ignore")).hexdigest()

        new_analysis = {
            "error": full_traceback,
            "suggestion": suggestion,
            "timestamp": timestamp,
            "first_seen": timestamp,
            "last_seen": timestamp,
            "repeat_count": 1,
            "error_signature": error_signature,
            "node_context": node_context.to_dict() if node_context else None,
            "analysis_metadata": analysis_metadata,
            "matched_pattern_id": matched_pattern_id,
            "pattern_category": pattern_category,
            "pattern_priority": pattern_priority,
            "resolution_status": "unresolved",
        }

        # R2: Thread-safe update of shared state
        with _history_lock:
            global _last_analysis
            _last_analysis = new_analysis
            # Aggregate repeated identical errors within 60 seconds to avoid unbounded history growth.
            # NOTE: We still update _last_analysis every time so the UI reflects new occurrences.
            aggregated = False
            try:
                now_ts = self._parse_ts(timestamp)
                # Look back across recent history to find a matching signature in-window.
                # Limit scan to keep cost bounded even when history is unbounded.
                scan_limit = 50
                hist_len = len(_analysis_history)
                start_index = max(0, hist_len - scan_limit)
                for i in range(hist_len - 1, start_index - 1, -1):
                    existing = _analysis_history[i]
                    if not isinstance(existing, dict):
                        continue
                    if existing.get("error_signature") != error_signature:
                        continue
                    last_seen_str = existing.get("last_seen") or existing.get("timestamp") or ""
                    last_seen_ts = self._parse_ts(last_seen_str)
                    if (now_ts - last_seen_ts).total_seconds() <= self._aggregate_window_seconds:
                        existing["repeat_count"] = int(existing.get("repeat_count", 1) or 1) + 1
                        existing["last_seen"] = timestamp
                        # Keep first_seen stable
                        if not existing.get("first_seen"):
                            existing["first_seen"] = existing.get("timestamp") or timestamp
                        aggregated = True
                    break
            except Exception:
                pass

            if not aggregated:
                _analysis_history.append(new_analysis.copy())

        # F1: Persist to history store
        try:
            store = _get_history_store()
            entry = HistoryEntry(
                timestamp=timestamp,
                error=full_traceback,
                suggestion=suggestion if suggestion else {},
                node_context=node_context.to_dict() if node_context else None,
                matched_pattern_id=matched_pattern_id,
                pattern_category=pattern_category,
                pattern_priority=pattern_priority,
                resolution_status="unresolved",
                analysis_metadata=analysis_metadata,
                repeat_count=1,
                first_seen=timestamp,
                last_seen=timestamp,
                error_signature=error_signature,
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
    _message_queue = DroppingQueue(maxsize=CONFIG.log_queue_maxsize)
    _log_processor = DoctorLogProcessor(_message_queue)
    _log_processor.start()

    # Save original streams (may already be ComfyUI's LogInterceptor)
    _original_stdout = sys.stdout
    _original_stderr = sys.stderr

    # Wrap stdout/stderr
    sys.stdout = SafeStreamWrapper(_original_stdout, _message_queue)
    sys.stderr = SafeStreamWrapper(_original_stderr, _message_queue)

    # ComfyUI Desktop (and some ComfyUI builds) install StreamHandler(s) before Doctor,
    # capturing the original sys.stdout/sys.stderr object (often LogInterceptor).
    # If that stream's flush() raises (e.g., OSError 22), Python logging will emit a traceback
    # for EVERY log record, causing massive log spam and filling Doctor history with noise.
    #
    # Patch existing StreamHandler streams to wrap them in a flush-safe proxy.
    try:
        root_logger = logging.getLogger()
        for handler in list(getattr(root_logger, "handlers", []) or []):
            stream = getattr(handler, "stream", None)
            if stream in (_original_stdout, _original_stderr) or getattr(type(stream), "__name__", "") == "LogInterceptor":
                handler.stream = FlushSafeProxy(stream)
    except Exception:
        pass

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
    if _message_queue:
        _message_queue.clear()
    _message_queue = None

    logging.info("[Doctor] Logger uninstalled")


def get_logger_metrics() -> Dict[str, Any]:
    """Return logger health metrics for diagnostics and tests."""
    metrics = {
        "queue_size": 0,
        "queue_dropped_total": 0,
        "queue_dropped_priority": 0,
        "queue_dropped_non_priority": 0,
        "queue_dropped_oldest": 0,
        "buffer_dropped": 0,
        "traceback_resets": 0,
        "queue_timeouts": 0,
    }

    if _message_queue:
        metrics.update(_message_queue.get_stats())
        metrics["queue_size"] = _message_queue.qsize()

    if _log_processor:
        metrics.update(_log_processor._metrics)

    return metrics


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
