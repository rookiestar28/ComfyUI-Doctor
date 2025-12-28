"""
Smart Logger for ComfyUI Runtime Diagnostics.
Intercepts stdout/stderr to capture logs and provide real-time error analysis.
"""

import sys
import datetime
import threading
import queue
import time
from collections import deque
from typing import Optional, Dict, Any, TextIO, List
from weakref import finalize
from .analyzer import ErrorAnalyzer
from .config import CONFIG


# Global state for API access
_last_analysis: Dict[str, Any] = {
    "error": None,
    "suggestion": None,
    "timestamp": None,
    "node_context": None,  # NodeContext.to_dict() result
}

# P1: Error history buffer (ring buffer for last N errors)
_analysis_history: deque = deque(maxlen=CONFIG.history_size)


def get_last_analysis() -> Dict[str, Any]:
    """Get the last error analysis result for API access."""
    return _last_analysis.copy()


def get_analysis_history() -> List[Dict[str, Any]]:
    """Get the error analysis history (most recent first)."""
    return list(reversed(_analysis_history))


class AsyncFileWriter:
    """
    Asynchronous file writer using a background thread.
    Batches writes to reduce I/O overhead and prevent main thread blocking.
    """
    
    def __init__(self, filepath: str):
        self._queue: queue.Queue = queue.Queue()
        self._file = open(filepath, "a", encoding="utf-8")
        self._running = True
        self._thread = threading.Thread(target=self._writer_loop, daemon=True)
        self._thread.start()
        self._finalizer = finalize(self, self._cleanup, self._file, self._queue)
    
    @staticmethod
    def _cleanup(file_handle, write_queue):
        """Safe cleanup: flush remaining queue and close file."""
        try:
            # Drain remaining messages
            batch = []
            while True:
                try:
                    batch.append(write_queue.get_nowait())
                except queue.Empty:
                    break
            if batch and file_handle and not file_handle.closed:
                file_handle.writelines(batch)
                file_handle.flush()
                file_handle.close()
        except Exception:
            pass
    
    def write(self, message: str) -> None:
        """Non-blocking write: enqueue message for background processing."""
        if self._running:
            self._queue.put(message)
    
    def _writer_loop(self) -> None:
        """Background thread: batch dequeue and write to file."""
        while self._running:
            try:
                # Block until at least one message is available
                first_msg = self._queue.get(timeout=0.5)
                batch = [first_msg]
                
                # Drain additional messages (non-blocking)
                while True:
                    try:
                        batch.append(self._queue.get_nowait())
                    except queue.Empty:
                        break
                
                # Batch write
                self._file.writelines(batch)
                self._file.flush()
                
            except queue.Empty:
                continue
            except Exception:
                pass
    
    def flush(self) -> None:
        """Force flush: wait for queue to drain (with timeout)."""
        deadline = time.time() + 1.0  # 1 second max wait
        while not self._queue.empty() and time.time() < deadline:
            time.sleep(0.01)
    
    def close(self) -> None:
        """Stop the writer thread and close the file."""
        self._running = False
        self._thread.join(timeout=2.0)  # Wait for background thread to complete
        self._finalizer()


class SmartLogger:
    """
    A smart logger that intercepts stdout/stderr, writes to file,
    and provides real-time error analysis with suggestions.
    Uses async file writing to prevent main thread I/O blocking.
    """
    
    _original_stdout = None
    _original_stderr = None
    _instances = []
    _async_writer: Optional[AsyncFileWriter] = None

    def __init__(self, filepath: str, stream: TextIO):
        """
        Initialize the SmartLogger.
        
        Args:
            filepath: Path to the log file.
            stream: Original stream to forward output to (stdout or stderr).
        """
        self.stream = stream
        self.filepath = filepath
        
        # Use shared async writer for all instances
        if SmartLogger._async_writer is None:
            SmartLogger._async_writer = AsyncFileWriter(filepath)
        
        self.buffer: list[str] = []
        self.in_traceback = False
        self._last_buffer_time = 0.0
        self.lock = threading.Lock()  # Only for traceback buffer, not for I/O
        
        SmartLogger._instances.append(self)

    @classmethod
    def install(cls, log_path: str):
        """Safely install the logger, preventing multiple hooks."""
        if cls._original_stdout is None:
            cls._original_stdout = sys.stdout
        if cls._original_stderr is None:
            cls._original_stderr = sys.stderr
        
        # Prevent double wrapping
        if not isinstance(sys.stdout, cls):
            sys.stdout = cls(log_path, cls._original_stdout)
        
        if not isinstance(sys.stderr, cls):
            sys.stderr = cls(log_path, cls._original_stderr)

    @classmethod
    def uninstall(cls):
        """Restore original streams and close async writer."""
        if cls._original_stdout:
            sys.stdout = cls._original_stdout
        if cls._original_stderr:
            sys.stderr = cls._original_stderr
            
        # Close shared async writer
        if cls._async_writer:
            cls._async_writer.close()
            cls._async_writer = None
        
        cls._instances.clear()

    def write(self, message: str) -> None:
        """Write message to both console and log file, analyzing for errors."""
        # 1. Output to original stream (Console) - synchronous for immediate feedback
        try:
            self.stream.write(message)
            self.stream.flush()
        except Exception:
            pass 
        
        # 2. Write to log file - async (non-blocking)
        if SmartLogger._async_writer:
            SmartLogger._async_writer.write(message)

        # 3. Analyze for errors (uses lock only for traceback buffer)
        with self.lock:
            self._analyze_stream(message)

    def _analyze_stream(self, message: str) -> None:
        """
        Analyze the stream for Python tracebacks and provide suggestions.
        Uses improved detection logic to ensure complete tracebacks.
        """
        current_time = time.time()
        
        # P3 Fix: Urgent single-line warnings from Debug Node (Immediate analysis)
        if "❌ CRITICAL" in message or "⚠️ Meta Tensor" in message:
             suggestion = ErrorAnalyzer.analyze(message)
             if suggestion:
                 self._record_analysis(message, suggestion)
             return
        
        # Detect start of error block (Traceback OR Validation Error)
        if "Traceback (most recent call last):" in message or "Failed to validate prompt for output" in message:
            self.in_traceback = True
            self.buffer = [message]
            self._last_buffer_time = current_time
            return

        if self.in_traceback:
            # P0 Fix: Check timeout BEFORE updating timestamp
            if current_time - self._last_buffer_time > CONFIG.traceback_timeout_seconds:
                 # P2 Fix: Try to analyze buffer before discarding (for non-standard errors)
                 full_traceback = "".join(self.buffer)
                 
                 # Analyze without requiring strict completeness check first
                 suggestion = ErrorAnalyzer.analyze(full_traceback)
                 
                 # Only record if we found something useful or it strongly looks like an error
                 if suggestion or "Failed to validate" in full_traceback:
                     self._record_analysis(full_traceback, suggestion)
                 
                 self.in_traceback = False
                 self.buffer = []
                 # Don't return here, technically current message could be start of new error, 
                 # but for simplicity we treat it as normal log if we just timed out.
            
            else:
                self.buffer.append(message)
                self._last_buffer_time = current_time
                
                # Build full text for analysis
                full_traceback = "".join(self.buffer)
                
                # Check for completeness
                if ErrorAnalyzer.is_complete_traceback(full_traceback):
                    suggestion = ErrorAnalyzer.analyze(full_traceback)
                    self._record_analysis(full_traceback, suggestion)
                    
                    # Reset state
                    self.in_traceback = False
                    self.buffer = []
                
                # Safety: Prevent buffer from growing too large
                elif len(self.buffer) > CONFIG.buffer_limit:
                    self.in_traceback = False
                    self.buffer = []

    def _record_analysis(self, full_traceback, suggestion):
        """Helper to record analysis result and print formatted output."""
        node_context = ErrorAnalyzer.extract_node_context(full_traceback)
        
        # Update global state for API access
        global _last_analysis
        _last_analysis = {
            "error": full_traceback,
            "suggestion": suggestion,
            "timestamp": datetime.datetime.now().isoformat(),
            "node_context": node_context.to_dict() if node_context else None,
        }
        
        # Add to history buffer
        _analysis_history.append(_last_analysis.copy())
        
        # Only print if we have something useful to say (Context OR Suggestion)
        # This prevents empty boxes for unhandled system errors (like shutdown noise)
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
        
        # Add suggestion
        if suggestion:
            output_parts.append(suggestion)
        
        output_parts.append(f"{'-'*40}\n")
        
        formatted_output = "\n".join(output_parts)
        
        # Write format box to both streams (Raw error was already written)
        try:
            self.stream.write(formatted_output)
            if SmartLogger._async_writer:
                SmartLogger._async_writer.write(formatted_output)
        except Exception:
            pass

    def flush(self) -> None:
        """Flush both streams."""
        try:
            self.stream.flush()
            if SmartLogger._async_writer:
                SmartLogger._async_writer.flush()
        except Exception:
            pass
            
    def close(self) -> None:
        """Close is handled by class-level uninstall."""
        pass  # No-op: async writer is shared and closed via uninstall()
    
    # Required for proper stream compatibility
    @property
    def encoding(self) -> Optional[str]:
        """Return the encoding of the underlying stream."""
        return getattr(self.stream, 'encoding', 'utf-8')
    
    def isatty(self) -> bool:
        """Check if the stream is a TTY."""
        return getattr(self.stream, 'isatty', lambda: False)()
    
    def fileno(self) -> int:
        """Return the file descriptor of the underlying stream."""
        try:
            return self.stream.fileno()
        except Exception:
            return -1
